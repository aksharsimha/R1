import streamlit as st
import edu_db
from risk_analyzer import load_holdings
from portfolio_ledger import HOLDINGS_FILE

def render(user_info):
    # Retrieve user & progress state
    display_name = user_info.get("display_name", "Thaneer Basha")
    progress = edu_db.load_progress()
    total_xp = progress.get("total_xp", 150)
    virtual_balance = progress.get("virtual_balance", 15000.0)
    badges = progress.get("badges", [])
    completed_articles = progress.get("completed_articles", [])
    
    # Calculate level info
    lvl_info = edu_db.get_level_info(total_xp)
    cur_lvl_num = lvl_info.get("level_number", 1)
    next_xp = lvl_info.get("next_xp", 500) or 500
    min_xp = lvl_info.get("min_xp", 0)
    progress_pct = lvl_info.get("progress_pct", 30.0)
    
    # Portfolio stats
    try:
        holdings = load_holdings(HOLDINGS_FILE)
        holdings_count = len(holdings)
    except Exception:
        holdings_count = 1
    
    markets_count = max(24, holdings_count * 4)
    watchlist_count = max(12, holdings_count * 2)
    alerts_count = 5
    achievements_count = f"{max(3, len(badges))} / 20"
    streak_days = progress.get("daily_streak", 7)
    weekly_goal = f"{min(5, max(2, len(completed_articles)))} / 5"

    st.markdown('''<style>
[data-testid="stSidebar"] { display: none !important; }
.stApp {
    background-color: #070712 !important;
    background-image: 
        radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.14) 0%, transparent 40%),
        radial-gradient(circle at 85% 20%, rgba(168, 85, 247, 0.16) 0%, transparent 45%),
        radial-gradient(circle at 50% 85%, rgba(59, 130, 246, 0.10) 0%, transparent 50%) !important;
    background-attachment: fixed !important;
    color: #f8fafc !important;
}
.hub-hero { text-align: center; padding-top: 1.2rem; padding-bottom: 0.8rem; }
.hub-hero-welcome { font-size: 1.25rem; font-weight: 500; color: #cbd5e1; margin-bottom: 0.25rem; letter-spacing: -0.2px; }
.hub-hero-title {
    font-size: 3.4rem; font-weight: 800; letter-spacing: -1px;
    background: linear-gradient(135deg, #a5f3fc 0%, #93c5fd 30%, #c084fc 70%, #f472b6 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0 0 0.4rem 0; line-height: 1.15;
}
.hub-hero-sub { font-size: 1.05rem; color: #94a3b8; font-weight: 400; margin-bottom: 1.2rem; }
.hub-card-box {
    background: rgba(13, 15, 28, 0.75); backdrop-filter: blur(16px);
    border: 1px solid rgba(139, 92, 246, 0.22); border-radius: 20px;
    padding: 1.6rem 1.6rem 1.4rem 1.6rem;
    box-shadow: 0 12px 35px -8px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    transition: all 0.28s ease; position: relative; height: 100%;
    display: flex; flex-direction: column; justify-content: space-between;
}
.hub-card-box:hover {
    border-color: rgba(168, 85, 247, 0.45);
    box-shadow: 0 16px 45px -8px rgba(124, 58, 237, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    transform: translateY(-2px);
}
.hub-card-box.edu-theme { border-color: rgba(59, 130, 246, 0.22); }
.hub-card-box.edu-theme:hover {
    border-color: rgba(59, 130, 246, 0.45);
    box-shadow: 0 16px 45px -8px rgba(37, 99, 235, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
.hub-card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.2rem; }
.hub-card-header-left { display: flex; align-items: center; gap: 14px; }
.hub-card-icon {
    width: 44px; height: 44px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center; font-size: 1.3rem;
}
.hub-card-icon.prof {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(124, 58, 237, 0.4));
    border: 1px solid rgba(168, 85, 247, 0.35); box-shadow: 0 0 15px rgba(139, 92, 246, 0.3);
}
.hub-card-icon.edu {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(37, 99, 235, 0.4));
    border: 1px solid rgba(96, 165, 250, 0.35); box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
}
.hub-card-title { font-size: 1.25rem; font-weight: 700; color: #ffffff; margin: 0 0 2px 0; letter-spacing: -0.3px; }
.hub-card-subtitle { font-size: 0.82rem; color: #94a3b8; margin: 0; }
.hub-card-arrow-btn {
    width: 32px; height: 32px; border-radius: 8px;
    background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08);
    display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 0.9rem;
}
.hub-featured-box {
    background: rgba(8, 10, 20, 0.65); border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px; padding: 1.2rem; margin-bottom: 1.2rem;
    display: flex; align-items: center; justify-content: space-between; position: relative; overflow: hidden;
}
.hub-stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 1.2rem; }
.hub-stat-grid-2 { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; margin-bottom: 1.2rem; }
.hub-mini-stat {
    background: rgba(18, 20, 36, 0.6); border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px; padding: 10px 12px; display: flex; align-items: center; gap: 10px;
}
.hub-mini-stat-label { font-size: 0.68rem; color: #94a3b8; font-weight: 500; text-transform: uppercase; letter-spacing: 0.4px; }
.hub-mini-stat-val { font-size: 1rem; font-weight: 700; color: #ffffff; }
div[data-testid="stColumn"]:nth-of-type(1) div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 50%, #a855f7 100%) !important;
    color: #ffffff !important; border: none !important; border-radius: 12px !important;
    font-weight: 600 !important; font-size: 1rem !important; height: 48px !important;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.45) !important; transition: all 0.25s ease !important;
}
div[data-testid="stColumn"]:nth-of-type(1) div.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 25px rgba(168, 85, 247, 0.65) !important; transform: translateY(-1px) !important;
}
div[data-testid="stColumn"]:nth-of-type(2) div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 50%, #3b82f6 100%) !important;
    color: #ffffff !important; border: none !important; border-radius: 12px !important;
    font-weight: 600 !important; font-size: 1rem !important; height: 48px !important;
    box-shadow: 0 4px 20px rgba(37, 99, 235, 0.45) !important; transition: all 0.25s ease !important;
}
div[data-testid="stColumn"]:nth-of-type(2) div.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 25px rgba(59, 130, 246, 0.65) !important; transform: translateY(-1px) !important;
}
</style>''', unsafe_allow_html=True)

    # 1. Header Hero
    st.markdown(f'''<div class="hub-hero">
<div class="hub-hero-welcome">Welcome back,</div>
<h1 class="hub-hero-title">{display_name}.</h1>
<div class="hub-hero-sub">Pick up where you left off and keep leveling up. 🚀</div>
</div>''', unsafe_allow_html=True)

    # 2. Pill Navigation Bar (Interactive Quick Actions)
    p_spacer_l, p1, p2, p3, p4, p_spacer_r = st.columns([1.2, 1, 1, 1.1, 1, 1.2])
    with p1:
        if st.button("📊  Analytics", key="hub_pill_analytics", use_container_width=True):
            st.query_params["workspace"] = "professional"
            st.query_params["page"] = "Analytics"
            st.rerun()
    with p2:
        if st.button("📈  Progress", key="hub_pill_progress", use_container_width=True):
            st.query_params["workspace"] = "education"
            st.query_params["page"] = "Learning Path"
            st.rerun()
    with p3:
        if st.button("🏆  Achievements", key="hub_pill_achievements", use_container_width=True):
            st.query_params["workspace"] = "education"
            st.query_params["page"] = "Badges"
            st.rerun()
    with p4:
        if st.button("🎯  Goals", key="hub_pill_goals", use_container_width=True):
            st.query_params["workspace"] = "professional"
            st.query_params["page"] = "Planner"
            st.rerun()

    st.markdown("<div style='margin-bottom: 1.2rem;'></div>", unsafe_allow_html=True)

    # 3. Two Main Hub Cards
    card_col1, card_col2 = st.columns(2, gap="large")

    # ── Left Card: Professional Portfolio ─────────────────────────────────────
    with card_col1:
        svg_growth_chart = '<svg width="150" height="90" viewBox="0 0 150 90" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="barGrad1" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#8b5cf6"/><stop offset="100%" stop-color="#4c1d95"/></linearGradient><linearGradient id="barGrad2" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#a78bfa"/><stop offset="100%" stop-color="#6d28d9"/></linearGradient><linearGradient id="barGrad3" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#c084fc"/><stop offset="100%" stop-color="#7c3aed"/></linearGradient><linearGradient id="arrowGrad" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#a855f7"/><stop offset="100%" stop-color="#e879f9"/></linearGradient><filter id="glowEffect" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3" result="blur"/><feComposite in="SourceGraphic" in2="blur" operator="over"/></filter></defs><rect x="25" y="60" width="14" height="24" rx="3" fill="url(#barGrad1)" /><rect x="45" y="48" width="14" height="36" rx="3" fill="url(#barGrad1)" /><rect x="65" y="38" width="14" height="46" rx="3" fill="url(#barGrad2)" /><rect x="85" y="26" width="14" height="58" rx="3" fill="url(#barGrad2)" /><rect x="105" y="14" width="14" height="70" rx="3" fill="url(#barGrad3)" /><path d="M15 68 Q 50 54 80 32 T 128 10" fill="none" stroke="url(#arrowGrad)" stroke-width="3.5" stroke-linecap="round" filter="url(#glowEffect)"/><polygon points="122,8 136,8 132,22" fill="#e879f9" filter="url(#glowEffect)"/></svg>'

        html_prof_card = f'''<div class="hub-card-box">
<div>
<div class="hub-card-top">
<div class="hub-card-header-left">
<div class="hub-card-icon prof">💼</div>
<div>
<div class="hub-card-title">Professional Portfolio</div>
<div class="hub-card-subtitle">Track markets. Analyze risk. Grow your wealth.</div>
</div>
</div>
<div class="hub-card-arrow-btn">↗</div>
</div>
<div class="hub-featured-box">
<div>
<div style="font-size:0.75rem;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">STATUS</div>
<div style="font-size:1.35rem;font-weight:700;color:#38bdf8;margin-bottom:8px;">Active Environment</div>
<div style="display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);border-radius:999px;padding:3px 10px;">
<div style="width:7px;height:7px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;"></div>
<span style="font-size:0.75rem;font-weight:600;color:#34d399;">All systems operational</span>
</div>
</div>
<div>{svg_growth_chart}</div>
</div>
<div class="hub-stat-grid">
<div class="hub-mini-stat">
<span style="font-size:1.1rem;color:#a855f7;">📊</span>
<div>
<div class="hub-mini-stat-label">Markets Tracked</div>
<div class="hub-mini-stat-val">{markets_count}</div>
</div>
</div>
<div class="hub-mini-stat">
<span style="font-size:1.1rem;color:#818cf8;">⭐</span>
<div>
<div class="hub-mini-stat-label">Watchlist</div>
<div class="hub-mini-stat-val">{watchlist_count}</div>
</div>
</div>
<div class="hub-mini-stat">
<span style="font-size:1.1rem;color:#f43f5e;">🔔</span>
<div>
<div class="hub-mini-stat-label">Alerts</div>
<div class="hub-mini-stat-val">{alerts_count}</div>
</div>
</div>
<div class="hub-mini-stat">
<span style="font-size:1.1rem;color:#38bdf8;">⏱</span>
<div>
<div class="hub-mini-stat-label">Last Updated</div>
<div class="hub-mini-stat-val" style="font-size:0.88rem;">2m ago</div>
</div>
</div>
</div>
</div>
</div>'''
        st.markdown(html_prof_card, unsafe_allow_html=True)
        
        if st.button("Go to Portfolio →", key="hub_btn_go_portfolio", type="primary", use_container_width=True):
            st.query_params["workspace"] = "professional"
            st.query_params["page"] = "Overview"
            st.rerun()

    # ── Right Card: Games & Education ─────────────────────────────────────────
    with card_col2:
        html_edu_card = f'''<div class="hub-card-box edu-theme">
<div>
<div class="hub-card-top">
<div class="hub-card-header-left">
<div class="hub-card-icon edu">🎓</div>
<div>
<div class="hub-card-title">Games & Education</div>
<div class="hub-card-subtitle">Learn. Play. Achieve. Level up your skills.</div>
</div>
</div>
<div class="hub-card-arrow-btn">↗</div>
</div>
<div class="hub-featured-box">
<div style="flex:1;">
<div style="display:flex;justify-content:space-between;align-items:flex-start;">
<div>
<div style="font-size:0.75rem;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">YOUR PROGRESS</div>
<div style="font-size:1.35rem;font-weight:700;color:#fbbf24;margin-bottom:6px;">⭐ {total_xp} XP</div>
</div>
<div style="text-align:right;">
<div style="font-size:0.75rem;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">UP NEXT</div>
<div style="display:inline-flex;align-items:center;gap:6px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:8px;padding:4px 10px;">
<span style="color:#60a5fa;font-size:0.75rem;">▶</span>
<span style="font-size:0.85rem;font-weight:700;color:#ffffff;">Level {cur_lvl_num}</span>
</div>
</div>
</div>
<div style="margin-top:12px;">
<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#94a3b8;font-weight:600;margin-bottom:4px;">
<span>Progress</span>
<span>{total_xp} / {next_xp} XP</span>
</div>
<div style="width:100%;height:6px;background:rgba(255,255,255,0.08);border-radius:999px;overflow:hidden;">
<div style="width:{min(100.0, max(5.0, progress_pct))}%;height:100%;background:linear-gradient(90deg, #f59e0b, #fbbf24);border-radius:999px;"></div>
</div>
</div>
</div>
</div>
<div class="hub-stat-grid-2">
<div class="hub-mini-stat">
<span style="font-size:1.3rem;color:#34d399;">💳</span>
<div>
<div class="hub-mini-stat-label">Virtual Trading Balance</div>
<div class="hub-mini-stat-val" style="color:#34d399;">₹ {virtual_balance:,.0f}</div>
</div>
</div>
<div class="hub-mini-stat">
<span style="font-size:1.3rem;color:#c084fc;">🏆</span>
<div>
<div class="hub-mini-stat-label">Achievements</div>
<div class="hub-mini-stat-val">{achievements_count}</div>
</div>
</div>
</div>
</div>
</div>'''
        st.markdown(html_edu_card, unsafe_allow_html=True)

        if st.button("Resume Learning →", key="hub_btn_go_education", type="primary", use_container_width=True):
            st.query_params["workspace"] = "education"
            st.query_params["page"] = "Learning Path"
            st.rerun()

    # 4. Bottom Motivation Strip
    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
    
    bot_c1, bot_c2 = st.columns([3.8, 1.2])
    with bot_c1:
        st.markdown(f'''<div style="background: rgba(13, 15, 28, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 16px 0 0 16px; padding: 1.1rem 1.6rem; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5); min-height: 70px;">
<div style="display:flex;align-items:center;gap:12px;">
<span style="font-size:2.2rem;color:#6366f1;line-height:1;">❝</span>
<div style="font-size:0.95rem;color:#cbd5e1;font-weight:500;">
Small progress today, <span style="color:#60a5fa;font-weight:700;">big freedom</span> tomorrow.
</div>
</div>
<div style="display:flex;align-items:center;gap:2.5rem;">
<div style="display:flex;align-items:center;gap:10px;">
<span style="font-size:1.6rem;">🔥</span>
<div>
<div style="font-size:1.1rem;font-weight:700;color:#ffffff;line-height:1.1;">{streak_days}</div>
<div style="font-size:0.72rem;color:#94a3b8;font-weight:500;">Day Streak</div>
</div>
</div>
<div style="display:flex;align-items:center;gap:10px;">
<span style="font-size:1.6rem;color:#a855f7;">🎯</span>
<div>
<div style="font-size:1.1rem;font-weight:700;color:#ffffff;line-height:1.1;">{weekly_goal}</div>
<div style="font-size:0.72rem;color:#94a3b8;font-weight:500;">Weekly Goal</div>
</div>
</div>
</div>
</div>''', unsafe_allow_html=True)
    with bot_c2:
        st.markdown('''<div style="background: rgba(13, 15, 28, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.07); border-left: none; border-radius: 0 16px 16px 0; padding: 1.1rem 1.2rem; display: flex; align-items: center; justify-content: center; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5); min-height: 70px;">''', unsafe_allow_html=True)
        if st.button("View Achievements →", key="hub_btn_view_achievements", use_container_width=True):
            st.query_params["workspace"] = "education"
            st.query_params["page"] = "Badges"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
