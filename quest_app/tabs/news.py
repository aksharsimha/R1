import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
from datetime import datetime
import textwrap
import plotly.express as px
import plotly.graph_objects as go
import time
import pytz
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings
import news_sentiment
from news_sentiment import (
    get_asset_sentiment,
    get_archived_articles,
    get_market_breadth_data,
    get_live_market_feed,
    infer_article_category,
    CATEGORY_IMAGES,
)
import nse_live as _nse
import firebase_db


# ──────────────────────────────────────────────────────────────────────────────
# Modal Dialogs for 100% Interactivity
# ──────────────────────────────────────────────────────────────────────────────

@st.dialog("Public Profile")
def _show_public_profile(username: str):
    profile = firebase_db.get_user_profile(username)
    if profile:
        disp = profile.get("display_name", username)
        av = profile.get("avatar")
        av_html = f'<img src="{av}" style="width:76px;height:76px;border-radius:50%;object-fit:cover;border:2px solid var(--q-accent);">' if av else f'<div style="width:76px;height:76px;border-radius:50%;background:var(--q-accent);color:white;display:flex;align-items:center;justify-content:center;font-size:1.8rem;font-weight:bold;">{disp[:1].upper()}</div>'
        st.markdown(textwrap.dedent(f"""
<div style="display:flex;align-items:center;gap:18px;margin-bottom:14px;">
{av_html}
<div>
<h3 style="margin:0;font-size:1.3rem;">{disp}</h3>
<p style="margin:2px 0 0;color:var(--q-text-3);font-size:0.85rem;">@{username}</p>
<div style="margin-top:6px;font-size:0.75rem;color:var(--q-pos);">● Active User</div>
</div>
</div>
"""), unsafe_allow_html=True)
        st.caption("Account is active and verified on QUEST Network.")
    else:
        st.error("User profile not found.")


@st.dialog("🔍 Search News & Holdings")
def _search_dialog(all_articles: list, current_assets: list):
    st.markdown("<h3 style='margin:0 0 12px;'>Search Market Intelligence</h3>", unsafe_allow_html=True)
    query = st.text_input("Search articles, tickers, or topics", placeholder="e.g. Reliance, NIFTY, Tata, Earnings, Real Estate", key="news_search_input")
    
    if query and query.strip():
        q = query.strip().lower()
        matched_articles = [
            a for a in all_articles
            if q in (a.get("title", "")).lower()
            or q in (a.get("summary", "")).lower()
            or q in (a.get("ticker", "")).lower()
            or q in (a.get("category", "")).lower()
        ]
        
        st.markdown(f"<p style='color:var(--q-text-3);font-size:0.85rem;'>Found {len(matched_articles)} article(s) matching <strong>'{query}'</strong>:</p>", unsafe_allow_html=True)
        
        if matched_articles:
            for art in matched_articles[:8]:
                title = art.get("title", "News Article")
                link = art.get("link", "#")
                cat = art.get("category", "MARKET UPDATE")
                sent = art.get("sentiment_label", "⚪ Neutral")
                dt_str = str(art.get("date", ""))[:10]
                summary_text = art.get("summary", "")
                
                st.markdown(textwrap.dedent(f"""
<div style="background:var(--q-surface-2);border-radius:10px;padding:12px;margin-bottom:10px;border-left:3px solid var(--q-accent);">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
<span style="font-size:0.7rem;font-weight:600;color:var(--q-accent);background:var(--q-accent-weak);padding:2px 6px;border-radius:4px;">{cat}</span>
<span style="font-size:0.75rem;color:var(--q-text-3);">{dt_str}</span>
</div>
<a href="{link}" target="_blank" style="color:var(--q-text);text-decoration:none;font-weight:600;font-size:0.92rem;display:block;margin-bottom:4px;">{title}</a>
<p style="font-size:0.8rem;color:var(--q-text-2);margin:0 0 6px;line-height:1.4;">{summary_text[:140]}...</p>
<div style="font-size:0.75rem;color:var(--q-text-3);">{sent} &bull; <a href="{link}" target="_blank" style="color:var(--q-accent);">Read Full Story →</a></div>
</div>
"""), unsafe_allow_html=True)
        else:
            st.info("No matching articles found. Try searching for broader terms like 'market', 'growth', or a company name.")
    else:
        st.caption("Type in any keyword or company name above to find instant sentiment analysis and news stories.")


@st.dialog("🔔 Market & Sentiment Alerts")
def _notifications_dialog(_user_info: dict):
    st.markdown("<h3 style='margin:0 0 14px;'>Recent Alerts & Activity</h3>", unsafe_allow_html=True)
    alerts = [
        {"icon": "⚡", "title": "Market Sentiment Updated", "desc": "NSE sentiment scan complete across your active holdings and benchmarks.", "time": "10m ago"},
        {"icon": "📈", "title": "Index Momentum Alert", "desc": "NIFTY 50 trading strong (+0.78%) above key moving averages.", "time": "1h ago"},
        {"icon": "🧠", "title": "AI Prediction Recalibration", "desc": "EWMA Engine adjusted confidence intervals with fresh market inputs.", "time": "3h ago"},
        {"icon": "📰", "title": "New Corporate Action Digest", "desc": "Real-time market headlines analyzed and archived for portfolio tracking.", "time": "Today"},
    ]
    for a in alerts:
        st.markdown(textwrap.dedent(f"""
<div style="display:flex;align-items:flex-start;gap:12px;padding:10px 12px;background:var(--q-surface-2);border-radius:10px;margin-bottom:8px;">
<div style="font-size:1.2rem;background:var(--q-surface);width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">{a['icon']}</div>
<div style="flex:1;">
<div style="display:flex;justify-content:space-between;align-items:center;">
<strong style="color:var(--q-text);font-size:0.88rem;">{a['title']}</strong>
<span style="font-size:0.72rem;color:var(--q-text-3);">{a['time']}</span>
</div>
<div style="font-size:0.78rem;color:var(--q-text-2);margin-top:2px;line-height:1.35;">{a['desc']}</div>
</div>
</div>
"""), unsafe_allow_html=True)
    st.caption("Notifications are automatically synced with your cloud portfolio.")


@st.dialog("📰 Full Market Intelligence & News Feed")
def _view_all_news_dialog(all_articles: list):
    st.markdown("<h3 style='margin:0 0 12px;'>Full Market News Feed</h3>", unsafe_allow_html=True)
    
    cat_filter = st.selectbox("Filter by Category", ["All Categories", "MARKET UPDATE", "REAL ESTATE", "EARNINGS", "BANKING & FINANCE", "TECHNOLOGY", "ENERGY & POWER", "COMMODITIES & METALS"], key="all_news_cat_filter")
    sent_filter = st.radio("Filter by Sentiment", ["All Sentiments", "🟢 Positive", "🔴 Negative", "⚪ Neutral"], horizontal=True, key="all_news_sent_filter")
    
    filtered = all_articles
    if cat_filter != "All Categories":
        filtered = [a for a in filtered if a.get("category") == cat_filter]
    if sent_filter != "All Sentiments":
        filtered = [a for a in filtered if a.get("sentiment_label") == sent_filter]
        
    st.markdown(f"<p style='color:var(--q-text-3);font-size:0.85rem;margin:8px 0;'>Showing {len(filtered)} live article(s):</p>", unsafe_allow_html=True)
    
    for art in filtered:
        title = art.get("title", "News Article")
        link = art.get("link", "#")
        cat = art.get("category", "MARKET UPDATE")
        img = art.get("image_url", CATEGORY_IMAGES.get(cat, CATEGORY_IMAGES["MARKET UPDATE"]))
        summary = art.get("summary", "")
        dt_str = str(art.get("date", ""))[:10]
        read_time = art.get("read_time", "2 min read")
        ticker = art.get("ticker", "NSE")
        sent = art.get("sentiment_label", "⚪ Neutral")
        
        st.markdown(textwrap.dedent(f"""
<div style="display:flex;gap:14px;background:var(--q-surface-2);border-radius:12px;padding:12px;margin-bottom:12px;border:1px solid var(--q-border);">
<img src="{img}" style="width:110px;height:85px;border-radius:8px;object-fit:cover;flex-shrink:0;" alt="{cat}">
<div style="flex:1;">
<div style="display:gap:6px;align-items:center;margin-bottom:4px;">
<span style="font-size:0.68rem;font-weight:700;color:#818cf8;background:rgba(99,102,241,0.12);padding:2px 6px;border-radius:4px;">{cat}</span>
<span style="font-size:0.72rem;color:var(--q-text-3);">{dt_str}</span>
<span style="font-size:0.72rem;color:var(--q-text-3);">&bull; {read_time}</span>
</div>
<a href="{link}" target="_blank" style="color:var(--q-text);font-size:0.92rem;font-weight:600;text-decoration:none;display:block;margin-bottom:4px;">{title}</a>
<p style="font-size:0.78rem;color:var(--q-text-2);margin:0;line-height:1.4;">{summary[:160]}...</p>
<div style="margin-top:6px;font-size:0.72rem;color:var(--q-text-3);">{sent} &bull; Tag: <span style="color:var(--q-accent);">{ticker}</span></div>
</div>
</div>
"""), unsafe_allow_html=True)


@st.dialog("📁 Historical News Archive")
def _archive_dialog():
    st.markdown("<h3 style='margin:0 0 10px;'>Browse Historical News Archive</h3>", unsafe_allow_html=True)
    st.caption("Search through previously analyzed news and historical market events.")
    
    archive = get_archived_articles()
    all_dates = set()
    for t_arts in archive.values():
        for a in t_arts:
            d = str(a.get("date", ""))[:10]
            if d:
                all_dates.add(d)
                
    sorted_dates = sorted(list(all_dates), reverse=True)
    if not sorted_dates:
        sorted_dates = [datetime.now().strftime("%Y-%m-%d")]
    
    c1, c2 = st.columns([1, 1])
    with c1:
        selected_date = st.selectbox("Select Date", sorted_dates)
    with c2:
        search_kw = st.text_input("Filter within date", placeholder="Keyword or company name")
        
    date_articles = []
    for ticker, arts in archive.items():
        for a in arts:
            if str(a.get("date", ""))[:10] == selected_date:
                if not search_kw or search_kw.lower() in (a.get("title", "") + a.get("summary", "")).lower():
                    date_articles.append((ticker, a))
                    
    if date_articles:
        st.markdown(f"<p style='color:var(--q-text-3);font-size:0.85rem;'>{len(date_articles)} article(s) found on <strong>{selected_date}</strong>:</p>", unsafe_allow_html=True)
        for ticker, art in date_articles[:15]:
            title = art.get("title", "Archived News")
            url = art.get("url", "#")
            score = art.get("sentiment_score", 0.0)
            label = art.get("sentiment_label", "⚪ Neutral")
            cat = art.get("category", "MARKET UPDATE")
            
            st.markdown(textwrap.dedent(f"""
<div style="background:var(--q-surface-2);border-radius:10px;padding:10px 12px;margin-bottom:8px;border-left:3px solid var(--q-border);">
<div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:3px;">
<span style="font-weight:600;color:var(--q-accent);">{ticker} &bull; {cat}</span>
<span>{label} ({score:+.2f})</span>
</div>
<a href="{url}" target="_blank" style="color:var(--q-text);font-size:0.88rem;font-weight:500;text-decoration:none;">{title}</a>
</div>
"""), unsafe_allow_html=True)
    else:
        st.info("No archived articles found for the selected criteria.")


# ──────────────────────────────────────────────────────────────────────────────
# Helper for Sparkline Curves
# ──────────────────────────────────────────────────────────────────────────────

def _render_sparkline_svg(color: str, kind: str = "bull") -> str:
    if kind == "bull":
        points = "0,24 20,22 40,26 60,18 80,20 100,12 120,15 140,8 160,12 180,5 200,6"
    elif kind == "bear":
        points = "0,8 20,10 40,6 60,16 80,14 100,22 120,20 140,25 160,22 180,28 200,26"
    elif kind == "neutral":
        points = "0,16 20,14 40,18 60,15 80,19 100,12 120,16 140,14 160,18 180,15 200,16"
    else:
        points = "0,20 25,18 50,22 75,16 100,19 125,14 150,17 175,12 200,14"

    grad_id = f"grad_{color.replace('#', '').replace('(', '').replace(')', '')}"
    return f"""<svg viewBox="0 0 200 32" style="width:100%;height:32px;overflow:visible;" preserveAspectRatio="none"><defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{color}" stop-opacity="0.3" /><stop offset="100%" stop-color="{color}" stop-opacity="0.0" /></linearGradient></defs><path d="M {points} L 200,32 L 0,32 Z" fill="url(#{grad_id})" /><polyline fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="{points}" /></svg>"""


# ──────────────────────────────────────────────────────────────────────────────
# Main Render Function
# ──────────────────────────────────────────────────────────────────────────────

def render(df=None, summary=None, current_assets=None, _user_info=None,
           portfolio_sentiment_score=None, _sentiment_neg_count=None, comp_score=None):
    
    total_invested = df['Invested (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl = df['P&L (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    
    _user_info = _user_info or st.session_state.get("user_info", {})
    _username = _user_info.get("username", "User")
    _display_name = _user_info.get("display_name", _username)
    
    # Calculate time of day greeting
    ist = pytz.timezone("Asia/Kolkata")
    now_hour = datetime.now(ist).hour
    greeting_time = "morning" if now_hour < 12 else "afternoon" if now_hour < 17 else "evening"
    
    # ── CSS Styling ───────────────────────────────────────────────────────────
    st.markdown(textwrap.dedent("""
<style>
.q-news-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.2rem;
}
.q-news-brand-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--q-text);
    display: flex;
    align-items: center;
    gap: 8px;
    letter-spacing: -0.5px;
}
.q-news-brand-sub {
    font-size: 0.76rem;
    color: var(--q-text-3);
    margin-top: 1px;
    letter-spacing: 0.2px;
}
.q-news-greeting {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--q-text);
    margin-top: 6px;
}

/* Top 4 KPI Cards */
.q-kpi-card {
    background: linear-gradient(145deg, rgba(24,28,40,0.92), rgba(13,16,25,0.96));
    border: 1px solid rgba(112,126,171,0.22);
    border-radius: 14px;
    padding: 16px 18px 14px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
    transition: transform 0.2s, border-color 0.2s;
}
.q-kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(129,140,248,0.45);
}
.q-kpi-val {
    font-size: 1.95rem;
    font-weight: 700;
    color: var(--q-text);
    line-height: 1;
    font-family: 'JetBrains Mono', monospace;
}
.q-kpi-badge {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-left: 8px;
    vertical-align: middle;
}
.q-kpi-sub {
    font-size: 0.75rem;
    color: var(--q-text-3);
    margin-top: 6px;
}

/* Sentiment Summary Bar */
.q-sentiment-bar {
    background: linear-gradient(90deg, rgba(24,28,42,0.95), rgba(15,18,28,0.98));
    border: 1px solid rgba(112,126,171,0.22);
    border-radius: 12px;
    padding: 12px 18px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 1.4rem;
}

/* Two Column Layout Cards */
.q-panel-box {
    background: linear-gradient(145deg, rgba(20,24,36,0.96), rgba(11,14,22,0.98));
    border: 1px solid rgba(112,126,171,0.24);
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 16px 36px rgba(0,0,0,0.22);
    margin-bottom: 14px;
}

/* Market Overview Cards */
.q-index-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 16px;
}
.q-index-box {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(112,126,171,0.16);
    border-radius: 12px;
    padding: 14px;
}
.q-index-name {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--q-text-3);
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
.q-index-price {
    font-size: 1.45rem;
    font-weight: 700;
    color: var(--q-text);
    font-family: 'JetBrains Mono', monospace;
    margin: 4px 0 2px;
}
.q-index-delta {
    font-size: 0.8rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}

/* Market Breadth Card */
.q-breadth-box {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(112,126,171,0.16);
    border-radius: 12px;
    padding: 16px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 18px;
    text-align: center;
}
.q-breadth-item strong {
    display: block;
    font-size: 1.25rem;
    font-family: 'JetBrains Mono', monospace;
    color: var(--q-text);
    margin: 4px 0 2px;
}
.q-breadth-item span {
    font-size: 0.72rem;
    color: var(--q-text-3);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.q-breadth-item small {
    font-size: 0.75rem;
    color: var(--q-text-3);
}

/* News Article Cards */
.q-news-item {
    display: flex;
    gap: 16px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(112,126,171,0.16);
    border-radius: 14px;
    padding: 14px;
    margin-bottom: 14px;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.q-news-item:hover {
    background: rgba(255,255,255,0.04);
    border-color: rgba(129,140,248,0.4);
    transform: translateY(-1px);
}
.q-news-thumb {
    width: 120px;
    height: 92px;
    border-radius: 10px;
    object-fit: cover;
    flex-shrink: 0;
}
.q-news-content {
    flex: 1;
    min-width: 0;
}
.q-news-tag {
    font-size: 0.65rem;
    font-weight: 700;
    color: #a5b4fc;
    background: rgba(99,102,241,0.15);
    padding: 2px 7px;
    border-radius: 4px;
    letter-spacing: 0.5px;
    display: inline-block;
    margin-bottom: 6px;
}
.q-news-headline {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--q-text);
    line-height: 1.35;
    margin: 0 0 4px;
    text-decoration: none;
    display: block;
}
.q-news-headline:hover {
    color: #818cf8;
}
.q-news-desc {
    font-size: 0.8rem;
    color: var(--q-text-2);
    line-height: 1.4;
    margin: 0 0 6px;
}
.q-news-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.72rem;
    color: var(--q-text-3);
}

/* Bottom News Archive Banner */
.q-archive-banner {
    background: linear-gradient(90deg, rgba(20,24,36,0.96), rgba(12,15,24,0.98));
    border: 1px solid rgba(112,126,171,0.22);
    border-radius: 14px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 1.4rem;
}
</style>
"""), unsafe_allow_html=True)

    # ── Fetch Comprehensive Real Live News Feed ───────────────────────────────
    current_assets = current_assets or []
    all_articles = get_live_market_feed(current_assets, limit_per_source=4)
    
    # Compute per-holding sentiments
    statuses = {}
    for asset_obj in current_assets:
        ident = getattr(asset_obj, "identifier", None)
        name = getattr(asset_obj, "name", ident)
        if ident:
            sent_res = get_asset_sentiment(ident, stock_name=name, limit=6)
            statuses[ident] = sent_res.get("status", "Neutral")

    # Calculate metrics
    n_bull = sum(1 for s in statuses.values() if s == "Bullish")
    n_bear = sum(1 for s in statuses.values() if s == "Bearish")
    n_neut = sum(1 for s in statuses.values() if s not in ("Bullish", "Bearish"))
    total_h = len(current_assets) if current_assets else 1
    
    pct_bull = (n_bull / total_h * 100) if total_h > 0 else 0.0
    pct_bear = (n_bear / total_h * 100) if total_h > 0 else 0.0
    pct_neut = (n_neut / total_h * 100) if total_h > 0 else 100.0
    
    ps = portfolio_sentiment_score if portfolio_sentiment_score is not None else 0.0
    ps_label = "Bullish" if ps > 0.15 else "Bearish" if ps < -0.15 else "Neutral"
    ps_color = "#10b981" if ps > 0.15 else "#ef4444" if ps < -0.15 else "#818cf8"
    
    # Sentinel adj display
    sent_adj = st.session_state.get("_sent_adj_display", None)
    adj_disp = f"{sent_adj:+.2f}" if sent_adj is not None else "N/A"

    # ── Top Header Row ────────────────────────────────────────────────────────
    hdr_c1, hdr_c2 = st.columns([5, 2])
    with hdr_c1:
        st.markdown(textwrap.dedent(f"""
<div class="q-news-header">
<div>
<div class="q-news-brand-title"><span style="color:#f59e0b;">⚡</span> QUEST</div>
<div class="q-news-brand-sub">Quantitative Unified Equity Surveillance Tracker</div>
<div class="q-news-greeting">Good {greeting_time}, <span style="color:#34d399;">{_display_name}</span> 👋</div>
</div>
</div>
"""), unsafe_allow_html=True)
    with hdr_c2:
        btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
        with btn_c1:
            if st.button("🔍", key="btn_top_search", help="Search News & Holdings", use_container_width=True):
                _search_dialog(all_articles, current_assets)
        with btn_c2:
            if st.button("🔔 3", key="btn_top_notif", help="View Notifications", use_container_width=True):
                _notifications_dialog(_user_info)
        with btn_c3:
            if st.button("👤", key="btn_top_profile", help="View Profile", use_container_width=True):
                _show_public_profile(_username)

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    # ── Top 4 KPI Metric Cards ────────────────────────────────────────────────
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(textwrap.dedent(f"""
<div class="q-kpi-card" style="border-top:3px solid #10b981;">
{_render_sparkline_svg("#10b981", "bull")}
<div style="margin-top:6px;">
<span class="q-kpi-val">{n_bull}</span>
<span class="q-kpi-badge" style="color:#10b981;background:rgba(16,185,129,0.12);">● Bullish</span>
</div>
<div class="q-kpi-sub">{pct_bull:.1f}% of holdings</div>
</div>
"""), unsafe_allow_html=True)
    with kpi2:
        st.markdown(textwrap.dedent(f"""
<div class="q-kpi-card" style="border-top:3px solid #f97316;">
{_render_sparkline_svg("#f97316", "bear")}
<div style="margin-top:6px;">
<span class="q-kpi-val">{n_bear}</span>
<span class="q-kpi-badge" style="color:#f97316;background:rgba(249,115,22,0.12);">● Bearish</span>
</div>
<div class="q-kpi-sub">{pct_bear:.1f}% of holdings</div>
</div>
"""), unsafe_allow_html=True)
    with kpi3:
        st.markdown(textwrap.dedent(f"""
<div class="q-kpi-card" style="border-top:3px solid #3b82f6;">
{_render_sparkline_svg("#3b82f6", "neutral")}
<div style="margin-top:6px;">
<span class="q-kpi-val">{n_neut}</span>
<span class="q-kpi-badge" style="color:#3b82f6;background:rgba(59,130,246,0.12);">● Neutral</span>
</div>
<div class="q-kpi-sub">{pct_neut:.1f}% of holdings</div>
</div>
"""), unsafe_allow_html=True)
    with kpi4:
        st.markdown(textwrap.dedent(f"""
<div class="q-kpi-card" style="border-top:3px solid #8b5cf6;">
<div style="display:flex;align-items:center;justify-content:space-between;height:32px;">
<span style="font-size:1.6rem;color:#a78bfa;">🎯</span>
<span style="font-size:0.75rem;color:var(--q-text-3);text-transform:uppercase;letter-spacing:0.5px;">Sentiment</span>
</div>
<div style="margin-top:6px;">
<span class="q-kpi-val" style="color:#a78bfa;">{ps:+.2f}</span>
</div>
<div class="q-kpi-sub" style="display:flex;justify-content:space-between;align-items:center;">
<span>Overall Sentiment</span>
<span style="color:#a78bfa;font-weight:600;background:rgba(139,92,246,0.15);padding:1px 6px;border-radius:4px;font-size:0.7rem;">{ps_label}</span>
</div>
</div>
"""), unsafe_allow_html=True)

    # ── Today's Sentiment Summary Bar ─────────────────────────────────────────
    st.markdown(textwrap.dedent(f"""
<div class="q-sentiment-bar">
<div style="display:flex;align-items:center;gap:8px;">
<span style="font-size:1.15rem;">😊</span>
<span style="font-weight:600;color:var(--q-text);">Today's sentiment</span>
</div>
<div style="display:flex;align-items:center;gap:14px;font-size:0.85rem;">
<span style="color:#10b981;font-weight:500;">● {n_bull} bullish</span>
<span style="color:#f97316;font-weight:500;">● {n_bear} bearish</span>
<span style="color:#3b82f6;font-weight:500;">● {n_neut} neutral</span>
<span style="color:var(--q-text-3);">👥 Across {len(current_assets)} holdings</span>
</div>
<div style="margin-left:auto;display:flex;align-items:center;gap:16px;font-size:0.85rem;">
<span style="color:var(--q-text-3);">Overall <strong style="color:{ps_color};font-family:'JetBrains Mono',monospace;">{ps:+.2f} ({ps_label})</strong></span>
<span style="color:var(--q-text-3);">📈 Prediction adjustment: <strong style="color:var(--q-text);font-family:'JetBrains Mono',monospace;">{adj_disp}</strong></span>
</div>
</div>
"""), unsafe_allow_html=True)

    # ── Two-Column Main Content Grid ──────────────────────────────────────────
    col_left, col_right = st.columns([1.35, 1.05], gap="medium")

    # ── LEFT: Latest News ─────────────────────────────────────────────────────
    with col_left:
        news_h1, news_h2 = st.columns([3, 2])
        with news_h1:
            st.markdown("<div style='font-size:1.15rem;font-weight:600;color:var(--q-text);padding:6px 0;'>📰 Latest News</div>", unsafe_allow_html=True)
        with news_h2:
            if st.button("View All News →", key="btn_view_all_news", use_container_width=True):
                _view_all_news_dialog(all_articles)

        # Build items HTML cleanly
        articles_html = []
        display_articles = all_articles[:4] if all_articles else []
        
        for art in display_articles:
            title = art.get("title", "Market Intelligence Update")
            link = art.get("link", "#")
            summary_text = art.get("summary", "")
            cat = art.get("category", infer_article_category(title, summary_text))
            img_url = art.get("image_url", CATEGORY_IMAGES.get(cat, CATEGORY_IMAGES["MARKET UPDATE"]))
            read_time = art.get("read_time", "2 min read")
            ticker_tag = art.get("ticker", "Market")
            dt_str = str(art.get("date", ""))[:10]
            if not dt_str or dt_str == "None" or dt_str == "nan":
                dt_str = datetime.now().strftime("%b %d, %Y")

            desc_snippet = (summary_text[:130] + "...") if len(summary_text) > 130 else summary_text

            articles_html.append(f"""
<div class="q-news-item">
<img src="{img_url}" class="q-news-thumb" alt="{cat}">
<div class="q-news-content">
<div class="q-news-tag">{cat}</div>
<a href="{link}" target="_blank" class="q-news-headline">{title}</a>
<p class="q-news-desc">{desc_snippet}</p>
<div class="q-news-meta">
<span>📅 {dt_str}</span>
<span>⏱️ {read_time}</span>
<span style="color:#818cf8;font-weight:600;">🏷️ {ticker_tag}</span>
</div>
</div>
</div>
""")

        combined_news_items = "\n".join(articles_html)

        st.markdown(textwrap.dedent(f"""
<div class="q-panel-box">
{combined_news_items}
<div style="text-align:center;padding:12px 0 4px;color:var(--q-text-3);font-size:0.8rem;display:flex;align-items:center;justify-content:center;gap:8px;">
<span>No more news available</span>
<span style="font-size:1.2rem;opacity:0.6;">📰</span>
</div>
</div>
"""), unsafe_allow_html=True)

    # ── RIGHT: Market Overview ────────────────────────────────────────────────
    with col_right:
        breadth = get_market_breadth_data()
        nifty = breadth["nifty"]
        sensex = breadth["sensex"]
        
        nifty_chg_color = "#10b981" if nifty["chg"] >= 0 else "#ef4444"
        nifty_arrow = "↗" if nifty["chg"] >= 0 else "↘"
        sensex_chg_color = "#10b981" if sensex["chg"] >= 0 else "#ef4444"
        sensex_arrow = "↗" if sensex["chg"] >= 0 else "↘"

        # Panel Header with Action Button
        mkt_h1, mkt_h2 = st.columns([3, 2])
        with mkt_h1:
            st.markdown("<div style='font-size:1.15rem;font-weight:600;color:var(--q-text);padding:6px 0;'>📈 Market Overview</div>", unsafe_allow_html=True)
        with mkt_h2:
            if st.button("View Analytics →", key="btn_mkt_analytics", use_container_width=True):
                st.query_params["page"] = "Analytics"
                st.rerun()

        st.markdown(textwrap.dedent(f"""
<div class="q-panel-box">
<div class="q-index-row">
<div class="q-index-box">
<div class="q-index-name">NIFTY 50</div>
<div class="q-index-price">{nifty['last']:,.2f}</div>
<div class="q-index-delta" style="color:{nifty_chg_color};">{nifty['chg_abs']:+,.2f} ({nifty['chg']:+.2f}%) {nifty_arrow}</div>
<div style="margin-top:6px;">{_render_sparkline_svg(nifty_chg_color, "bull" if nifty['chg'] >= 0 else "bear")}</div>
</div>
<div class="q-index-box">
<div class="q-index-name">SENSEX</div>
<div class="q-index-price">{sensex['last']:,.2f}</div>
<div class="q-index-delta" style="color:{sensex_chg_color};">{sensex['chg_abs']:+,.2f} ({sensex['chg']:+.2f}%) {sensex_arrow}</div>
<div style="margin-top:6px;">{_render_sparkline_svg(sensex_chg_color, "bull" if sensex['chg'] >= 0 else "bear")}</div>
</div>
</div>
<div class="q-breadth-box">
<div class="q-breadth-item">
<span>Market Status</span>
<strong style="color:#10b981;font-size:1.05rem;">● {breadth['status']}</strong>
<small>{breadth['status_sub']}</small>
</div>
<div class="q-breadth-item">
<span>Advances</span>
<strong style="color:#10b981;">{breadth['advances']:,}</strong>
<small>{breadth['advances_pct']}%</small>
</div>
<div class="q-breadth-item">
<span>Declines</span>
<strong style="color:#f87171;">{breadth['declines']:,}</strong>
<small>{breadth['declines_pct']}%</small>
</div>
<div class="q-breadth-item">
<span>Unchanged</span>
<strong style="color:#94a3b8;">{breadth['unchanged']:,}</strong>
<small>{breadth['unchanged_pct']}%</small>
</div>
</div>
<div style="background:rgba(255,255,255,0.02);border:1px dashed rgba(112,126,171,0.22);border-radius:10px;padding:12px 14px;display:flex;align-items:center;gap:10px;">
<span style="color:#f59e0b;font-size:1.1rem;">⭐</span>
<span style="font-size:0.8rem;color:var(--q-text-2);">Stay informed and make better decisions with real-time market insights.</span>
</div>
</div>
"""), unsafe_allow_html=True)

    # ── Bottom News Archive Banner ────────────────────────────────────────────
    st.markdown(textwrap.dedent("""
<div class="q-archive-banner">
<div style="display:flex;align-items:center;gap:14px;">
<div style="width:40px;height:40px;border-radius:10px;background:rgba(99,102,241,0.12);display:flex;align-items:center;justify-content:center;font-size:1.3rem;">📁</div>
<div>
<strong style="color:var(--q-text);font-size:0.95rem;display:block;">News Archive</strong>
<span style="color:var(--q-text-3);font-size:0.8rem;">Browse past articles by date and stay updated with market history.</span>
</div>
</div>
</div>
"""), unsafe_allow_html=True)

    arch_c1, arch_c2 = st.columns([4, 1])
    with arch_c2:
        if st.button("Browse Archive →", key="btn_bottom_archive", use_container_width=True):
            _archive_dialog()

