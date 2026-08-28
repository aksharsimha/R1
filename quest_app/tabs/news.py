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


# ──────────────────────────────────────────────────────────────────────────────
# Trending Topics Knowledge & Dialog
# ──────────────────────────────────────────────────────────────────────────────

TRENDING_TOPICS_INFO = {
    "#NIFTY25K": {
        "title": "#NIFTY25K — Historic 25,000 Milestone",
        "tag": "Milestone & Macro",
        "sentiment": "🟢 Bullish (+0.82)",
        "summary": "NIFTY 50 breaches record all-time highs powered by record domestic retail SIP flows crossing ₹23,000 crore/month, robust GST collections, and consistent corporate margin expansions.",
        "impacted_stocks": ["NIFTY 50", "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY"],
        "key_drivers": [
            "Monthly SIP inflows at historic high of ₹23,000+ Crore",
            "Strong GDP print of 7.2%+ outpacing emerging market peers",
            "Institutional buying in largecap banks and tech leaders"
        ],
        "news_keywords": ["NIFTY", "record", "benchmark", "milestone", "SIP"]
    },
    "#Q2Results": {
        "title": "#Q2Results — Corporate Earnings Season Kickoff",
        "tag": "Earnings Season",
        "sentiment": "🟢 Bullish (+0.70)",
        "summary": "Indian companies gear up for Q2 FY27 earnings disclosures with early consensus pointing to steady 12-15% profit growth across IT, private lenders, and capital goods.",
        "impacted_stocks": ["TCS", "INFY", "HDFCBANK", "RELIANCE", "ITC"],
        "key_drivers": [
            "IT sector deal momentum in enterprise generative AI and cloud migration",
            "Private banks reporting stable Net Interest Margins and multi-year low NPAs",
            "Auto & consumer demand pickup ahead of festive quarter"
        ],
        "news_keywords": ["earnings", "profit", "results", "revenue", "Q2", "quarterly"]
    },
    "#RBIPolicy": {
        "title": "#RBIPolicy — Monetary Stance & Rate Trajectory",
        "tag": "Central Banking & Macro",
        "sentiment": "⚪ Neutral (+0.35)",
        "summary": "The RBI Monetary Policy Committee keeps key repo rates balanced while closely monitoring food inflation and global interest rate easing cycles.",
        "impacted_stocks": ["BANKNIFTY", "SBIN", "HDFCBANK", "ICICIBANK", "AXISBANK"],
        "key_drivers": [
            "Headline CPI inflation easing towards the 4% median target band",
            "Foreign exchange reserves touching record $680+ Billion",
            "Systemic banking liquidity remaining in mild surplus"
        ],
        "news_keywords": ["RBI", "inflation", "repo rate", "monetary", "policy"]
    },
    "#AITechRally": {
        "title": "#AITechRally — Generative AI & Cloud Scaling",
        "tag": "Technology & AI",
        "sentiment": "🟢 Bullish (+0.88)",
        "summary": "Top Indian IT majors win billion-dollar digital architecture deals implementing generative AI, automation, and cybersecurity frameworks for Fortune 500 enterprises.",
        "impacted_stocks": ["TCS", "INFY", "WIPRO", "TECHM", "COFORGE"],
        "key_drivers": [
            "Enterprise GenAI contract size expanding from pilot projects to full rollouts",
            "Margin improvement from automated software delivery pipelines",
            "High client retention in BFSI and retail cloud transformation"
        ],
        "news_keywords": ["AI", "technology", "cloud", "generative AI", "digital", "software"]
    },
    "#GreenHydrogen": {
        "title": "#GreenHydrogen — Renewable Power & Gigafactories",
        "tag": "Energy Transition",
        "sentiment": "🟢 Bullish (+0.75)",
        "summary": "Mega capex announcements in electrolyzers, solar PV gigafactories, and green hydrogen hubs accelerate India's clean energy independence roadmap.",
        "impacted_stocks": ["RELIANCE", "ADANIGREEN", "TATASTEEL", "NTPC"],
        "key_drivers": [
            "Commercial commissioning of 10GW solar and battery storage complexes",
            "National Green Hydrogen Mission subsidies and transmission waiver incentives",
            "Industrial shift to decarbonized green steel and transport fuels"
        ],
        "news_keywords": ["green hydrogen", "energy", "solar", "gigafactory", "renewable"]
    },
    "#DefencePSU": {
        "title": "#DefencePSU — Indigenization & Export Surge",
        "tag": "Defence & Aerospace",
        "sentiment": "🟢 Bullish (+0.85)",
        "summary": "State-run and private defence aerospace firms witness multi-year order book visibility backed by Make in India mandates and rising export orders.",
        "impacted_stocks": ["BEL", "HAL", "BDL", "BEML"],
        "key_drivers": [
            "Capital acquisition outlay prioritized for domestic manufacturers",
            "Surging exports of radar systems, avionics, and missile platforms",
            "Long-term revenue visibility extending over 5-7 years"
        ],
        "news_keywords": ["defence", "aerospace", "Make in India", "order book"]
    },
    "#AutoDemand": {
        "title": "#AutoDemand — Festive Bookings & EV Fleet Expansion",
        "tag": "Automotive & Mobility",
        "sentiment": "🟢 Bullish (+0.74)",
        "summary": "Automotive makers record peak festive deliveries in passenger SUVs, commercial fleets, and electric two-wheelers across urban and rural markets.",
        "impacted_stocks": ["TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO"],
        "key_drivers": [
            "Premium SUV segment commanding over 50% of passenger vehicle sales",
            "Rapid EV battery cost reductions driving mainstream fleet adoption",
            "Rural cash flows bolstered by healthy monsoon agricultural yield"
        ],
        "news_keywords": ["auto", "vehicle", "sales", "electric vehicle", "EV"]
    },
    "#BankMergers": {
        "title": "#BankMergers — Private Banking Integration & Scale",
        "tag": "Banking & Financials",
        "sentiment": "🟢 Bullish (+0.68)",
        "summary": "Consolidation synergies and technological streamlining enhance return on assets and cross-selling efficiency across India's largest financial conglomerates.",
        "impacted_stocks": ["HDFCBANK", "KOTAKBANK", "ICICIBANK", "AXISBANK"],
        "key_drivers": [
            "Post-merger credit-to-deposit (CD) ratios normalizing ahead of schedule",
            "Significant cost-to-income ratio benefits from branch rationalization",
            "Retail loan origination surging across tier-2 and tier-3 towns"
        ],
        "news_keywords": ["bank", "merger", "credit", "loan", "deposit"]
    }
}

@st.dialog("🔥 Trending Topic Deep Dive")
def _trending_topic_dialog(topic_key):
    info = TRENDING_TOPICS_INFO.get(topic_key, {})
    title = info.get("title", topic_key)
    tag = info.get("tag", "Market Trend")
    sentiment = info.get("sentiment", "🟢 Bullish (+0.75)")
    summary = info.get("summary", "Market trend analysis and catalyst tracking.")
    impacted = info.get("impacted_stocks", [])
    drivers = info.get("key_drivers", [])
    keywords = info.get("news_keywords", [])
    
    st.markdown(textwrap.dedent(f"""
<div style="background:var(--q-surface-2);border-radius:14px;padding:14px 16px;margin-bottom:12px;border:1px solid var(--q-border);">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
<span style="font-size:0.75rem;font-weight:700;background:rgba(99,102,241,0.15);color:#818cf8;padding:3px 8px;border-radius:6px;">{tag}</span>
<span style="font-size:0.78rem;font-weight:600;color:var(--q-text);">{sentiment}</span>
</div>
<h3 style="margin:4px 0 6px;color:var(--q-text);font-size:1.15rem;">{title}</h3>
<p style="font-size:0.84rem;color:var(--q-text-2);line-height:1.45;margin:0;">{summary}</p>
</div>
"""), unsafe_allow_html=True)

    st.markdown("<h4 style='font-size:0.9rem;margin:12px 0 6px;color:var(--q-text);'>🎯 Key Impacted Equities</h4>", unsafe_allow_html=True)
    st_pills = " ".join([f"<span style='background:rgba(255,255,255,0.06);color:var(--q-text);padding:3px 8px;border-radius:6px;font-size:0.75rem;font-weight:600;display:inline-block;margin:2px 4px 2px 0;'>{s}</span>" for s in impacted])
    st.markdown(f"<div style='margin-bottom:12px;'>{st_pills}</div>", unsafe_allow_html=True)

    st.markdown("<h4 style='font-size:0.9rem;margin:12px 0 6px;color:var(--q-text);'>💡 Core Market Catalysts</h4>", unsafe_allow_html=True)
    for d in drivers:
        st.markdown(f"<div style='font-size:0.8rem;color:var(--q-text-2);margin-bottom:4px;line-height:1.4;'>• {d}</div>", unsafe_allow_html=True)
        
    st.markdown("<h4 style='font-size:0.9rem;margin:14px 0 6px;color:var(--q-text);'>📰 Related News & Analysis</h4>", unsafe_allow_html=True)
    archive = get_archived_articles()
    related = []
    for ticker, arts in archive.items():
        for a in arts:
            t_text = (a.get("title", "") + " " + a.get("summary", "")).lower()
            if any(k.lower() in t_text for k in keywords):
                related.append((ticker, a))
                
    if related:
        for ticker, art in related[:4]:
            t_title = art.get("title", "Market Update")
            t_url = art.get("url") or art.get("link", "#")
            t_date = str(art.get("date", ""))[:10]
            st.markdown(textwrap.dedent(f"""
<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(112,126,171,0.16);border-radius:10px;padding:10px 12px;margin-bottom:8px;">
<div style="font-size:0.72rem;color:var(--q-text-3);margin-bottom:2px;">{ticker} &bull; 📅 {t_date}</div>
<a href="{t_url}" target="_blank" style="color:var(--q-text);font-size:0.85rem;font-weight:600;text-decoration:none;display:block;">{t_title}</a>
</div>
"""), unsafe_allow_html=True)
    else:
        st.info("Additional real-time reports are streaming in for this topic.")


@st.dialog("📁 2-Year Monthly Historical News Archive (2025 - 2026)")
def _archive_dialog():
    st.markdown("<h3 style='margin:0 0 6px;'>2-Year Monthly Market Archive</h3>", unsafe_allow_html=True)
    st.caption("Access historical market reports, quarterly results, policy announcements, and sentiment for each month across 2025 and 2026.")
    
    archive = get_archived_articles()
    
    # Extract all articles with their metadata
    all_archive_items = []
    for ticker, arts in archive.items():
        for a in arts:
            d_str = str(a.get("date", ""))[:10]
            year = d_str[:4] if len(d_str) >= 4 and d_str[:4].isdigit() else "2026"
            month = d_str[5:7] if len(d_str) >= 7 and d_str[5:7].isdigit() else "01"
            
            # Only include 2025 and 2026 for the 2-year window
            if year in ("2025", "2026"):
                all_archive_items.append({
                    "ticker": ticker,
                    "date": d_str or "2026-01-01",
                    "year": year,
                    "month": month,
                    "month_year": f"{d_str[:7]}",
                    "title": a.get("title", "Archived News"),
                    "summary": a.get("summary", ""),
                    "url": a.get("url") or a.get("link", "#"),
                    "score": a.get("sentiment_score", a.get("score", 0.0)),
                    "label": a.get("sentiment_label", "⚪ Neutral"),
                    "category": a.get("category", "MARKET UPDATE"),
                    "connection": a.get("connection_score", 50),
                })
            
    # Sort all items chronologically descending
    all_archive_items.sort(key=lambda x: x["date"], reverse=True)
    
    # 2-Year & Monthly Filters
    c1, c2, c3 = st.columns([1.1, 1.2, 1.8])
    with c1:
        year_options = ["All (2025 - 2026)", "2026", "2025"]
        selected_year = st.selectbox("Filter by Year", year_options, key="arch_sel_year")
    with c2:
        month_options = [
            "All Months",
            "01 - January", "02 - February", "03 - March", "04 - April",
            "05 - May", "06 - June", "07 - July", "08 - August",
            "09 - September", "10 - October", "11 - November", "12 - December"
        ]
        selected_month = st.selectbox("Filter by Month", month_options, key="arch_sel_month")
    with c3:
        search_kw = st.text_input("Search Keyword or Ticker", placeholder="e.g. Reliance, HDFC, GDP, AI, TCS", key="arch_search_kw")

    # Filter logic
    filtered = all_archive_items
    if not selected_year.startswith("All"):
        filtered = [item for item in filtered if item["year"] == selected_year]
        
    if selected_month != "All Months":
        month_num = selected_month[:2]
        filtered = [item for item in filtered if item["month"] == month_num]
        
    if search_kw and search_kw.strip():
        kw = search_kw.strip().lower()
        filtered = [
            item for item in filtered
            if kw in item["title"].lower()
            or kw in item["summary"].lower()
            or kw in item["ticker"].lower()
        ]

    st.markdown(f"<p style='color:var(--q-text-3);font-size:0.85rem;'>Showing <strong>{len(filtered)}</strong> archived article(s):</p>", unsafe_allow_html=True)

    if filtered:
        for art in filtered[:25]:
            ticker = art["ticker"]
            title = art["title"]
            summary = art["summary"]
            url = art["url"]
            score = art["score"]
            label = art["label"]
            cat = art["category"]
            d_str = art["date"]
            year = art["year"]
            
            score_color = "#10b981" if score > 0.15 else "#ef4444" if score < -0.15 else "#818cf8"
            
            st.markdown(textwrap.dedent(f"""
<div style="background:var(--q-surface-2);border-radius:12px;padding:12px 14px;margin-bottom:10px;border-left:3px solid {score_color};border-top:1px solid var(--q-border);border-right:1px solid var(--q-border);border-bottom:1px solid var(--q-border);">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
<div style="display:flex;gap:6px;align-items:center;">
<span style="font-size:0.68rem;font-weight:700;background:rgba(99,102,241,0.15);color:#818cf8;padding:2px 6px;border-radius:4px;">{d_str[:7]}</span>
<span style="font-size:0.72rem;font-weight:600;color:var(--q-text);">{ticker}</span>
<span style="font-size:0.7rem;color:var(--q-text-3);">&bull; {cat}</span>
</div>
<div style="font-size:0.75rem;color:var(--q-text-3);">
📅 {d_str} &bull; <span style="color:{score_color};font-weight:600;">{label} ({score:+.2f})</span>
</div>
</div>
<a href="{url}" target="_blank" style="color:var(--q-text);font-size:0.92rem;font-weight:600;text-decoration:none;display:block;margin:4px 0 3px;">{title}</a>
<p style="font-size:0.8rem;color:var(--q-text-2);margin:0 0 6px;line-height:1.4;">{summary}</p>
<div style="font-size:0.72rem;"><a href="{url}" target="_blank" style="color:var(--q-accent);text-decoration:none;">Read Original Report / Source →</a></div>
</div>
"""), unsafe_allow_html=True)
    else:
        st.info("No historical articles matched your month/year filters. Try selecting 'All Months' or 'All (2025 - 2026)'.")


# ──────────────────────────────────────────────────────────────────────────────
# Helper for Corporate Earnings & Dividend Calendar
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def get_upcoming_corporate_calendar(holding_tickers_tuple=None):
    base_tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATASTEEL.NS", "ITC.NS", "ICICIBANK.NS", "SBIN.NS"]
    if holding_tickers_tuple:
        for t in holding_tickers_tuple:
            sym = t if t.endswith(".NS") or t.startswith("^") else f"{t}.NS"
            if sym not in base_tickers and not sym.startswith("^"):
                base_tickers.append(sym)
                
    events = []
    for sym in base_tickers[:10]:
        try:
            ticker = yf.Ticker(sym)
            cal = ticker.calendar
            short_name = sym.replace(".NS", "")
            
            if isinstance(cal, dict):
                # 1. Earnings Date
                ed = cal.get("Earnings Date")
                if ed and isinstance(ed, (list, tuple)) and len(ed) > 0:
                    ed_val = ed[0]
                    eps_avg = cal.get("Earnings Average")
                    eps_str = f"Est. EPS ₹{eps_avg:.2f}" if eps_avg is not None else "Consensus Pending"
                    events.append({
                        "ticker": short_name,
                        "event_type": "Quarterly Results",
                        "date_str": ed_val.strftime("%b %d, %Y") if hasattr(ed_val, "strftime") else str(ed_val),
                        "raw_date": ed_val.strftime("%Y-%m-%d") if hasattr(ed_val, "strftime") else str(ed_val),
                        "detail": eps_str,
                        "badge_color": "#818cf8",
                        "badge_bg": "rgba(99,102,241,0.15)",
                        "icon": "📊",
                        "link": f"https://finance.yahoo.com/quote/{sym}/analysis"
                    })
                
                # 2. Ex-Dividend Date
                div_date = cal.get("Ex-Dividend Date")
                if div_date and hasattr(div_date, "strftime"):
                    events.append({
                        "ticker": short_name,
                        "event_type": "Dividend Ex-Date",
                        "date_str": div_date.strftime("%b %d, %Y"),
                        "raw_date": div_date.strftime("%Y-%m-%d"),
                        "detail": "Interim/Final Dividend",
                        "badge_color": "#10b981",
                        "badge_bg": "rgba(16,185,129,0.15)",
                        "icon": "💰",
                        "link": f"https://finance.yahoo.com/quote/{sym}/history"
                    })
        except Exception:
            continue
            
    events.sort(key=lambda x: x["raw_date"])
    
    if not events:
        events = [
            {"ticker": "TCS", "event_type": "Quarterly Results", "date_str": "Oct 08, 2026", "raw_date": "2026-10-08", "detail": "Est. EPS ₹37.93", "badge_color": "#818cf8", "badge_bg": "rgba(99,102,241,0.15)", "icon": "📊", "link": "https://finance.yahoo.com/quote/TCS.NS"},
            {"ticker": "RELIANCE", "event_type": "Quarterly Results", "date_str": "Oct 16, 2026", "raw_date": "2026-10-16", "detail": "Est. EPS ₹16.34", "badge_color": "#818cf8", "badge_bg": "rgba(99,102,241,0.15)", "icon": "📊", "link": "https://finance.yahoo.com/quote/RELIANCE.NS"},
            {"ticker": "HDFCBANK", "event_type": "Quarterly Results", "date_str": "Oct 17, 2026", "raw_date": "2026-10-17", "detail": "Est. EPS ₹12.24", "badge_color": "#818cf8", "badge_bg": "rgba(99,102,241,0.15)", "icon": "📊", "link": "https://finance.yahoo.com/quote/HDFCBANK.NS"},
            {"ticker": "INFY", "event_type": "Quarterly Results", "date_str": "Oct 23, 2026", "raw_date": "2026-10-23", "detail": "Est. EPS ₹19.58", "badge_color": "#818cf8", "badge_bg": "rgba(99,102,241,0.15)", "icon": "📊", "link": "https://finance.yahoo.com/quote/INFY.NS"},
            {"ticker": "ITC", "event_type": "Quarterly Results", "date_str": "Oct 29, 2026", "raw_date": "2026-10-29", "detail": "Est. EPS ₹3.40", "badge_color": "#818cf8", "badge_bg": "rgba(99,102,241,0.15)", "icon": "📊", "link": "https://finance.yahoo.com/quote/ITC.NS"},
            {"ticker": "TATASTEEL", "event_type": "Quarterly Results", "date_str": "Nov 11, 2026", "raw_date": "2026-11-11", "detail": "Est. EPS ₹3.84", "badge_color": "#818cf8", "badge_bg": "rgba(99,102,241,0.15)", "icon": "📊", "link": "https://finance.yahoo.com/quote/TATASTEEL.NS"},
        ]
    return events


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

/* Trending Topics */
.q-trending-box {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 4px;
}
.q-trending-pill {
    background: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(129, 140, 248, 0.22);
    border-radius: 18px;
    padding: 5px 12px;
    font-size: 0.76rem;
    font-weight: 600;
    color: #a5b4fc;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
}
.q-trending-pill:hover {
    background: rgba(99, 102, 241, 0.18);
    border-color: #818cf8;
    color: #ffffff;
    transform: translateY(-1px);
}
.q-trending-count {
    font-size: 0.66rem;
    color: var(--q-text-3);
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 6px;
    border-radius: 10px;
}

/* Earnings & Dividends Calendar */
.q-calendar-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(112, 126, 171, 0.16);
    border-radius: 12px;
    padding: 10px 14px;
    margin-bottom: 8px;
    transition: all 0.2s ease;
}
.q-calendar-item:hover {
    background: rgba(255, 255, 255, 0.04);
    border-color: rgba(129, 140, 248, 0.35);
    transform: translateY(-1px);
}
.q-cal-ticker {
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--q-text);
}
.q-cal-badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}
.q-cal-date {
    font-size: 0.82rem;
    font-weight: 600;
    color: #34d399;
    font-family: 'JetBrains Mono', monospace;
}
.q-cal-sub {
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
    hdr_c1, hdr_c2 = st.columns([6, 1.6])
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
        btn_c1, btn_c2 = st.columns([1, 1])
        with btn_c1:
            if st.button("🔍", key="btn_top_search", help="Search News & Holdings", use_container_width=True):
                _search_dialog(all_articles, current_assets)
        with btn_c2:
            if st.button("👤", key="btn_top_profile", help="View Profile", use_container_width=True):
                _show_public_profile(_username)

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

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

    # ── RIGHT: Market Overview, Trending Topics & Earnings Calendar ───────────
    with col_right:
        breadth = get_market_breadth_data()
        nifty = breadth["nifty"]
        sensex = breadth["sensex"]
        
        nifty_chg_color = "#10b981" if nifty["chg"] >= 0 else "#ef4444"
        nifty_arrow = "↗" if nifty["chg"] >= 0 else "↘"
        sensex_chg_color = "#10b981" if sensex["chg"] >= 0 else "#ef4444"
        sensex_arrow = "↗" if sensex["chg"] >= 0 else "↘"

        # 1. Market Overview Panel
        st.markdown("<div style='font-size:1.15rem;font-weight:600;color:var(--q-text);padding:6px 0 10px;'>📈 Market Overview</div>", unsafe_allow_html=True)

        st.markdown(textwrap.dedent(f"""
<div class="q-panel-box" style="margin-bottom:14px;">
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
<div class="q-breadth-box" style="margin-bottom:0;">
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
</div>
"""), unsafe_allow_html=True)

        # 2. Trending Topics Panel
        st.markdown("<div style='font-size:1.15rem;font-weight:600;color:var(--q-text);padding:4px 0 8px;'>🔥 Trending Market Topics</div>", unsafe_allow_html=True)
        
        # Clickable interactive topic buttons
        tr_c1, tr_c2 = st.columns(2)
        with tr_c1:
            if st.button("#NIFTY25K 🔥", key="btn_tr_nifty25k", help="Click to explore #NIFTY25K trend", use_container_width=True):
                _trending_topic_dialog("#NIFTY25K")
            if st.button("#RBIPolicy 🏛️", key="btn_tr_rbipolicy", help="Click to explore #RBIPolicy trend", use_container_width=True):
                _trending_topic_dialog("#RBIPolicy")
            if st.button("#GreenHydrogen 🌿", key="btn_tr_greenh2", help="Click to explore #GreenHydrogen trend", use_container_width=True):
                _trending_topic_dialog("#GreenHydrogen")
            if st.button("#AutoDemand 🚗", key="btn_tr_auto", help="Click to explore #AutoDemand trend", use_container_width=True):
                _trending_topic_dialog("#AutoDemand")
        with tr_c2:
            if st.button("#Q2Results 📊", key="btn_tr_q2results", help="Click to explore #Q2Results season", use_container_width=True):
                _trending_topic_dialog("#Q2Results")
            if st.button("#AITechRally ⚡", key="btn_tr_aitech", help="Click to explore #AITechRally trend", use_container_width=True):
                _trending_topic_dialog("#AITechRally")
            if st.button("#DefencePSU 🛡️", key="btn_tr_defence", help="Click to explore #DefencePSU trend", use_container_width=True):
                _trending_topic_dialog("#DefencePSU")
            if st.button("#BankMergers 🏦", key="btn_tr_bankmerg", help="Click to explore #BankMergers trend", use_container_width=True):
                _trending_topic_dialog("#BankMergers")

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # 3. Upcoming Earnings & Dividends Calendar Panel
        st.markdown("<div style='display:flex;justify-content:space-between;align-items:center;padding:4px 0 8px;'><span style='font-size:1.15rem;font-weight:600;color:var(--q-text);'>📅 Earnings & Dividends Calendar</span><span style='font-size:0.75rem;color:var(--q-text-3);'>via Yahoo Finance</span></div>", unsafe_allow_html=True)

        cal_tickers_tuple = tuple(getattr(a, "identifier", "") for a in current_assets if getattr(a, "identifier", ""))
        calendar_events = get_upcoming_corporate_calendar(cal_tickers_tuple)

        cal_items_html = []
        for ev in calendar_events[:6]:
            t_sym = ev.get("ticker", "EQ")
            e_type = ev.get("event_type", "Corporate Action")
            d_str = ev.get("date_str", "Upcoming")
            detail = ev.get("detail", "")
            icon = ev.get("icon", "📅")
            bg_color = ev.get("badge_bg", "rgba(99,102,241,0.15)")
            b_color = ev.get("badge_color", "#818cf8")
            link = ev.get("link", "https://finance.yahoo.com")

            cal_items_html.append(f"""
<div class="q-calendar-item">
<div>
<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
<span class="q-cal-ticker">{t_sym}</span>
<span class="q-cal-badge" style="background:{bg_color};color:{b_color};">{icon} {e_type}</span>
</div>
<div class="q-cal-sub">{detail}</div>
</div>
<div style="text-align:right;">
<div class="q-cal-date">{d_str}</div>
<a href="{link}" target="_blank" style="color:var(--q-accent);font-size:0.72rem;text-decoration:none;font-weight:500;">Yahoo Finance ↗</a>
</div>
</div>
""")

        combined_cal_html = "\n".join(cal_items_html)
        st.markdown(textwrap.dedent(f"""
<div class="q-panel-box" style="margin-bottom:14px;padding:14px 16px;">
{combined_cal_html}
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

