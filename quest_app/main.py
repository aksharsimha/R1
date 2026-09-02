import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import sys
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from risk_analyzer import analyze_portfolio, generate_recommendations, load_holdings, save_holdings, DEFAULT_PORTFOLIO, Asset, AssetType, get_portfolio_growth
from portfolio_ledger import get_transactions, update_asset_holdings, update_asset_percentage, add_asset, remove_asset, HOLDINGS_FILE
from portfolio_ledger import save_daily_prediction, evaluate_past_predictions, get_predictions, ewma_catchup, confirm_manual_close
from news_sentiment import get_asset_sentiment, get_archived_articles
from adaptive_engine import adaptive_forecast, get_learning_log, get_days_trained

# --- Auth imports ---
from login_page import render_login_page
from auth import clear_remember_me, get_remembered_accounts, add_remembered_account, sync_cookies_to_browser
import chat_system
import portfolio_ledger
import adaptive_engine
import news_sentiment
import firebase_db

# --- Page Config ---
st.set_page_config(page_title="Portfolio Risk Monitor", page_icon="📈", layout="wide")
sync_cookies_to_browser()

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

# Upsert the active account without replacing any other remembered accounts.
if st.session_state.get("remember_me", True) and _username != "demo_guest":
    add_remembered_account(_username, _user_info.get("display_name"))

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

import edu_db
edu_db.set_data_dir(_user_data_dir, username=_username)

import tax_detective_db
tax_detective_db.set_data_dir(_user_data_dir, username=_username)

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

if st.session_state.get("just_logged_in"):
    st.session_state.just_logged_in = False
    # If the user logged in without an existing destination in URL, go to Hub
    if "page" not in st.query_params or not st.query_params.get("page"):
        st.query_params["page"] = "Hub"
    st.query_params.pop("return_to", None)
    _early_page = st.query_params.get("page", "Hub")
else:
    # On page refresh or direct navigation, strictly read page from URL query params
    _early_page = st.query_params.get("page", "Overview")
if _early_page == "AddAccount":
    from login_page import render_add_account_page
    render_add_account_page(st.query_params.get("return_to", "Overview"))
    st.stop()
if _early_page == "Settings":
    import quest_app.settings as settings
    st.sidebar.markdown("<div class='quest-settings-sidebar-title'>Settings</div>", unsafe_allow_html=True)
    if st.sidebar.button("← Dashboard", key="settings_dashboard_sidebar", use_container_width=True):
        _ws = st.query_params.get("workspace", "professional")
        st.query_params["page"] = edu_db.get_last_education_section() if _ws == "education" else edu_db.get_last_portfolio_section()
        st.rerun()
    st.sidebar.markdown("<div class='quest-nav-label'>Account</div>", unsafe_allow_html=True)
    _settings_section = st.sidebar.radio(
        "Settings sections", settings._SECTIONS, key="settings_sidebar_section",
        label_visibility="collapsed"
    )
    settings.render(_user_info, _settings_section)
    st.stop()

if _early_page == "Hub":
    import quest_app.tabs.hub as hub
    hub.render(_user_info)
    st.stop()

# Edu_Overview intercepts removed; now handled by native sidebar.

# --- Sidebar: profile, navigation, and account controls ---
import pytz
_hour = datetime.now(pytz.timezone('Asia/Kolkata')).hour
_greeting = "Good morning" if _hour < 12 else "Good afternoon" if _hour < 17 else "Good evening"
_avatar = _user_info.get("avatar")
if not _avatar:
    try:
        _my_p = firebase_db.get_user_profile(_username)
        if _my_p and _my_p.get("avatar"):
            _avatar = _my_p["avatar"]
            _user_info["avatar"] = _avatar
            st.session_state.user_info["avatar"] = _avatar
    except Exception:
        pass
_avatar_markup = (f'<img src="{_avatar}" alt="Profile avatar">' if _avatar else
                  f'<span>{_user_info.get("display_name", _username)[:1].upper()}</span>')

# BUG 2 FIX: Use real st.button() calls, NOT <a href> anchors.
# Raw anchors cause a full page navigation → session is lost → user lands on login.
# st.button() triggers a server-side rerun so the session is preserved.
st.sidebar.markdown('<div class="quest-icon-btn-row">', unsafe_allow_html=True)
if st.sidebar.button("⚙  Settings", key="sidebar_settings_btn", help="Open settings", use_container_width=True):
    st.session_state.nav_section = "⚙  Settings"
    st.query_params["page"] = "Settings"
    st.rerun()
st.sidebar.markdown('</div>', unsafe_allow_html=True)

_profile_placeholder = st.sidebar.empty()

try:
    _accounts = get_remembered_accounts()
except Exception:
    _accounts = []

# Deduplicate and ensure current active user is prioritized
_merged_accounts = []
_seen_lower = set()
for acc in [{"username": _username, "display_name": _user_info.get("display_name", _username)}] + _accounts:
    lower_name = acc["username"].lower()
    if lower_name not in _seen_lower:
        _seen_lower.add(lower_name)
        _merged_accounts.append(acc)

_accounts = _merged_accounts
if _username == "demo_guest":
    # Quarantine the demo user: NO account switcher allowed.
    st.sidebar.markdown(
        f"""
        <div style='padding: 10px 14px; background: rgba(255,255,255,0.05); border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 1rem;'>
            <div style='font-size: 0.9rem; font-weight: 600; color: #f8fafc;'>{_user_info.get('display_name', 'Demo User')}</div>
            <div style='font-size: 0.75rem; color: #94a3b8;'>@{_username}</div>
        </div>
        """, unsafe_allow_html=True
    )
else:
    _account_usernames = [account["username"] for account in _accounts]
    _account_labels = [f"{account['display_name']}  ·  @{account['username']}" for account in _accounts]
    _account_labels.append("+ Add account")
    _selected_account = st.sidebar.selectbox(
        "Switch account", _account_labels,
        index=_account_usernames.index(_username), key=f"switch_account_{_username}",
    )
    if _selected_account == "+ Add account":
        st.query_params["return_to"] = st.query_params.get("page", "Overview")
        st.query_params["page"] = "AddAccount"
        st.rerun()
    elif _selected_account in _account_labels:
        _selected_index = _account_labels.index(_selected_account)
        _selected_username = _account_usernames[_selected_index]
        if _selected_username != _username:
            _selected_info = _accounts[_selected_index]
            # Hydrate full profile from Firestore (cookie only has username/display_name)
            try:
                _switch_profile = firebase_db.get_user_profile(_selected_username)
                _switch_user_info = {
                    "username": _selected_info["username"],
                    "display_name": _switch_profile.get("display_name", _selected_info.get("display_name", _selected_info["username"])),
                    "uid": _switch_profile.get("uid", ""),
                    "email": _switch_profile.get("email", ""),
                }
                if _switch_profile.get("avatar"):
                    _switch_user_info["avatar"] = _switch_profile["avatar"]
            except Exception:
                _switch_user_info = {
                    "username": _selected_info["username"],
                    "display_name": _selected_info.get("display_name", _selected_info["username"]),
                }
            
            # Rule 5: Pin the active account to the end of the cookie so new tabs open to this account.
            if st.session_state.get("remember_me", True) and _switch_user_info["username"] != "demo_guest":
                add_remembered_account(_switch_user_info["username"], _switch_user_info.get("display_name"))
                
            # WIPE OLD CACHED DATA BEFORE RERUN TO PREVENT CROSS-ACCOUNT LEAKS
            for k in ["firebase_hydrated", "show_risk_breakdown", "_sentiment_score", "_sentiment_neg_count", "_sentiment_ts", "do_logout", "_analysis_df", "_analysis_summary", "_analysis_ts"]:
                if k in st.session_state:
                    del st.session_state[k]
                    
            st.session_state.authenticated = True
            st.session_state.user_info = _switch_user_info
            st.session_state.firebase_hydrated = False
            st.rerun()

# Sync navigation with URL query parameters to support Back/Forward buttons
_workspace = st.query_params.get("workspace", "professional")

# --- Sidebar: Workspace / Environment Switcher (Portfolio vs Games & Education) ---
st.sidebar.markdown("<div class='quest-nav-label'>Environment</div>", unsafe_allow_html=True)
_ws_col1, _ws_col2 = st.sidebar.columns(2, gap="small")
with _ws_col1:
    _is_prof = (_workspace == "professional")
    if st.button("💼 Portfolio", key="sidebar_switch_prof", type="primary" if _is_prof else "secondary", use_container_width=True):
        if not _is_prof:
            _last_prof = edu_db.get_last_portfolio_section()
            st.query_params["workspace"] = "professional"
            st.query_params["page"] = _last_prof
            st.rerun()
with _ws_col2:
    _is_edu = (_workspace == "education")
    if st.button("🎓 Education", key="sidebar_switch_edu", type="primary" if _is_edu else "secondary", use_container_width=True):
        if not _is_edu:
            _last_edu = edu_db.get_last_education_section()
            st.query_params["workspace"] = "education"
            st.query_params["page"] = _last_edu
            st.rerun()

if _workspace == "professional":
    _valid_pages = ["Overview", "Planner", "Analytics", "Projections", "Insights", "News", "Activity", "Chat", "MICHAEL", "Settings"]
    _page_labels = {
        "Overview": "⌂  Overview", "Planner": "◇  Planner", "Analytics": "◌  Analytics",
        "Projections": "↗  Projections", "Insights": "✦  Insights", "News": "◈  News",
        "Activity": "≡  Activity", "Chat": "◍  Chat", "MICHAEL": "◎  MICHAEL", "Settings": "⚙  Settings",
    }
    _sidebar_title = "Workspace"
    _default_page = edu_db.get_last_portfolio_section()
else:
    _valid_pages = ["Learning Path", "Library", "Virtual Trading", "Leaderboard", "Badges", "Tax Detective", "Settings"]
    _page_labels = {
        "Learning Path": "🎓  Learning Path", "Library": "📚  Knowledge Library",
        "Virtual Trading": "📈  Virtual Trading", "Leaderboard": "🏆  Leaderboard",
        "Badges": "🎖️  Badges", "Tax Detective": "🕵️  Tax Detective", "Settings": "⚙  Settings",
    }
    _sidebar_title = "Games & Education"
    _default_page = edu_db.get_last_education_section()

_query_page = st.query_params.get("page", _default_page)
if _query_page not in _valid_pages:
    _query_page = _default_page

_nav_pages = [page for page in _valid_pages if page != "Settings"]
_page_idx = _nav_pages.index(_query_page) if _query_page in _nav_pages else 0
_nav_labels = [_page_labels[page] for page in _nav_pages]

# Track workspace switches to reset nav state cleanly
if "last_active_workspace" not in st.session_state:
    st.session_state.last_active_workspace = _workspace

if st.session_state.last_active_workspace != _workspace:
    st.session_state.last_active_workspace = _workspace
    if "nav_section" in st.session_state:
        del st.session_state["nav_section"]

# Two-way sync: only sync nav_section from query params if query param changed programmatically
if "last_active_page" not in st.session_state:
    st.session_state.last_active_page = _query_page

if _query_page != st.session_state.last_active_page:
    st.session_state.last_active_page = _query_page
    target_lbl = _page_labels.get(_query_page)
    if target_lbl in _nav_labels:
        st.session_state.nav_section = target_lbl

st.sidebar.markdown(f"<div class='quest-nav-label'>{_sidebar_title}</div>", unsafe_allow_html=True)
_selected_label = st.sidebar.radio(
    "Navigate",
    _nav_labels,
    index=_page_idx,
    key=f"nav_section_{_workspace}_{_username}",
    label_visibility="collapsed",
)
section = ("Settings" if _query_page == "Settings" else
           next(page for page, label in _page_labels.items() if label == _selected_label))

# Persist last selected section for current user
if section != "Settings":
    if _workspace == "education":
        edu_db.set_last_education_section(section)
    elif _workspace == "professional":
        edu_db.set_last_portfolio_section(section)

# Update the URL if the user clicks a different page in sidebar
if section != _query_page:
    st.session_state.last_active_page = section
    st.query_params["page"] = section
    st.query_params["workspace"] = _workspace
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🏠  Main Hub", key="sidebar_goto_hub", use_container_width=True):
    st.query_params["page"] = "Hub"
    st.rerun()
st.sidebar.markdown("---")

# Streamlit owns the real collapse state; this replaces only its visible trigger.
st.markdown("""
<button id="quest-hamburger" aria-label="Toggle sidebar"><span></span><span></span><span></span></button>
<script>
(() => {
    const button = document.getElementById('quest-hamburger');
    if (!button || button.dataset.bound) return;
    button.dataset.bound = 'true';
    button.addEventListener('click', () => {
        const native = document.querySelector('[data-testid="stSidebarCollapseButton"]') ||
            document.querySelector('button[kind="header"]');
        if (native) native.click();
    });
})();
</script>
""", unsafe_allow_html=True)

if section == "Settings":
    import quest_app.settings as settings
    settings.render(_user_info)
    st.stop()

if section == "Learning Path":
    import quest_app.tabs.edu_overview as tb
    tb.render(_user_info)
    st.stop()

if section == "Library":
    import quest_app.tabs.education as tb
    tb.render(_user_info)
    st.stop()

if section == "Leaderboard":
    import quest_app.tabs.leaderboard as tb
    tb.render(_user_info)
    st.stop()

if section in ["Virtual Trading", "Badges", "Tax Detective"]:
    st.markdown(f"## {section} (Under Construction)")
    st.markdown("This tab is assigned to a team member and is currently being built.")
    st.stop()

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

# Analyze Data — cached in session_state so a full re-fetch + re-analysis
# only happens once every 180s (3m), not on every navigation or widget interaction.
_ANALYSIS_TTL = 180  # seconds
_now_ts_analysis = time.time()
_analysis_stale = (
    "_analysis_df" not in st.session_state
    or "_analysis_summary" not in st.session_state
    or (_now_ts_analysis - st.session_state.get("_analysis_ts", 0)) > _ANALYSIS_TTL
)

# If navigating to lightweight non-portfolio tab and cache is not ready, avoid blocking on fresh scrape
if section in ["Planner", "Chat", "Activity"] and "_analysis_df" not in st.session_state:
    st.session_state["_analysis_df"] = pd.DataFrame()
    st.session_state["_analysis_summary"] = {
        "total_value": 0.0, "portfolio_risk_score": 0.0,
        "portfolio_risk_bucket": "LOW", "n_assets": len(current_assets),
        "market_status": "Active", "market_open": True, "dominant_source": "cached"
    }
    st.session_state["_analysis_ts"] = _now_ts_analysis
    _analysis_stale = False

# ── Debug timing (visible only when ?debug=1 is in the URL) ──────────────────
_DEBUG = st.query_params.get("debug") == "1"
_dbg_t = {}  # timing accumulator: label -> elapsed seconds

with st.spinner("Analyzing portfolio data..."):
    try:
        if _analysis_stale:
            _t0 = time.time()
            df, summary = analyze_portfolio(current_assets, period="2y", verbose=False)
            _dbg_t["analyze_portfolio"] = time.time() - _t0
            st.session_state["_analysis_df"] = df
            st.session_state["_analysis_summary"] = summary
            st.session_state["_analysis_ts"] = _now_ts_analysis

            # ── Steps 1-3: EWMA + prediction grading — only when analysis refreshes ──
            # Gated by _analysis_stale so file I/O doesn't run on every widget click.
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

                # ── Step 2: EWMA catch-up ─────────────────────────────────────────
                # Scans ALL graded entries in predictions_log.json that are not yet
                # in adaptive_state.json's learning_log, and applies EWMA updates
                # immediately, regardless of when those entries were graded.
                _t0 = time.time()
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
                _dbg_t["ewma_and_evaluate"] = time.time() - _t0
        else:

            df = st.session_state["_analysis_df"]
            summary = st.session_state["_analysis_summary"]

        # FEATURE A: Update Profile Card with Growth Stat (runs every rerun — cheap)
        p_growth = get_portfolio_growth(df, summary)
        g_color = "#34d399" if p_growth["growth_abs"] >= 0 else "#f87171"
        g_sign = "+" if p_growth["growth_abs"] >= 0 else ""
        _profile_placeholder.markdown(f"""
        <div class="quest-profile-card">
            <div class="quest-profile-avatar">{_avatar_markup}</div>
            <div class="quest-profile-copy" style="flex:1;">
                <div class="quest-profile-name">{_user_info['display_name']}</div>
                <div class="quest-profile-user">@{_user_info['username']}</div>
            </div>
            <div style="text-align: right; line-height: 1.2;">
                <div style="font-size: 0.65rem; color: var(--q-text-3); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Growth</div>
                <div style="color: {g_color}; font-size: 0.85rem; font-weight: 600;">{g_sign}₹{p_growth["growth_abs"]:,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error fetching market data: {e}")
        st.stop()

# ── Portfolio Sentiment Score (cached 10 min so news isn’t re-fetched constantly) ──
# Compute once and store in session_state with a timestamp.
_SENT_TTL = 600  # seconds
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

        # Build list of assets that have an identifier
        _sent_assets = [_sa for _sa in current_assets if _sa.identifier]

        def _fetch_one_sentiment(_sa):
            """Fetch sentiment for a single asset; returns (asset, result_dict)."""
            return _sa, get_asset_sentiment(_sa.identifier, stock_name=_sa.name, limit=4)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        _t0 = time.time()
        with ThreadPoolExecutor(max_workers=8) as _sent_pool:
            _sent_futures = {_sent_pool.submit(_fetch_one_sentiment, _sa): _sa for _sa in _sent_assets}
            for _fut in as_completed(_sent_futures):
                try:
                    _sa, _sd = _fut.result()
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
        _dbg_t["sentiment_parallel"] = time.time() - _t0

        st.session_state['_sentiment_score'] = _sent_score_accum / _sent_weight_accum if _sent_weight_accum > 0 else 0.0
        st.session_state['_sentiment_neg_count'] = _sent_negative_count
        st.session_state['_sentiment_ts'] = _now_ts
    except Exception:
        st.session_state.setdefault('_sentiment_score', 0.0)
        st.session_state.setdefault('_sentiment_neg_count', 0)
        st.session_state['_sentiment_ts'] = _now_ts

# ── Debug timing panel — remove once timings are captured ─────────────────────
if _DEBUG and _dbg_t:
    st.markdown("---")
    st.markdown("**⏱ Debug Timings** *(remove `?debug=1` to hide)*")
    for _lbl, _elapsed in _dbg_t.items():
        st.write(f"• `{_lbl}`: **{_elapsed:.2f}s**")
    st.markdown("---")

portfolio_sentiment_score = st.session_state.get('_sentiment_score', 0.0)
_sentiment_neg_count = st.session_state.get('_sentiment_neg_count', 0)


# Top Metrics
total_invested = df["Invested (₹)"].sum() if not df.empty else 0.0
total_pnl = df["P&L (₹)"].sum() if not df.empty else 0.0
total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

comp_score = 0.0
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

# ── Section routing ──────────────────────────
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
    return section == _SEC_OF[name]

# Import tabs dynamically to avoid circular imports and keep startup fast
if _active("tab1"):
    import quest_app.tabs.overview_hero as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
    if st.session_state.show_risk_breakdown:
        import quest_app.tabs.risk_breakdown as rb
        rb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
    else:
        import quest_app.tabs.overview_holdings as tb_h
        tb_h.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)

elif _active("tab2"):
    import quest_app.tabs.analytics_compare as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif _active("tab_math"):
    import quest_app.tabs.analytics_metrics as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif _active("tab3"):
    import quest_app.tabs.insights as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif _active("tab4"):
    import quest_app.tabs.activity as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif _active("tab5"):
    import quest_app.tabs.projections as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif _active("tab6"):
    import importlib
    import quest_app.tabs.news as tb
    importlib.reload(tb)
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif _active("tab_chat"):
    import quest_app.tabs.chat as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif _active("tab_michael"):
    import importlib
    import quest_app.tabs.michael as tb
    importlib.reload(tb)
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif section == "Planner":
    import quest_app.tabs.planner as tb
    tb.render(df, summary, current_assets, _user_info, portfolio_sentiment_score, _sentiment_neg_count, comp_score)
elif section == "Learning Path":
    import quest_app.tabs.edu_overview as tb
    tb.render(_user_info)
elif section == "Library":
    import quest_app.tabs.education as tb
    tb.render(_user_info)
elif section == "Badges":
    import quest_app.tabs.badges as tb
    tb.render(_user_info)
elif section == "Tax Detective":
    import quest_app.tabs.tax_detective as tb
    tb.render(_user_info)
elif section in ["Virtual Trading", "Leaderboard"]:
    st.markdown(f"## {section} (Under Construction)")
    st.markdown("This tab is assigned to a team member and is currently being built.")
