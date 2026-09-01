import streamlit as st
import textwrap
import json
import os
import time
import edu_db
import news_sentiment
import nse_live as _nse

_HERE = os.path.dirname(os.path.abspath(__file__))
_CATALOG_PATH = os.path.join(os.path.dirname(_HERE), "education_catalog.json")
_QUIZZES_PATH = os.path.join(os.path.dirname(_HERE), "education_video_quizzes.json")

def _load_all_quizzes():
    if os.path.exists(_QUIZZES_PATH):
        try:
            with open(_QUIZZES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _get_active_video_info(current_level_id="level_1", completed_levels=None, watched_ids=None):
    """
    Returns the hero 'Up Next' info.
    - Picks the first module whose quiz hasn't been passed yet.
    - Within that module, picks the first video not yet watched.
    Falls back to first video of current_level_id if everything is done.
    """
    completed_levels = completed_levels or []
    watched_ids = set(watched_ids or [])

    if os.path.exists(_CATALOG_PATH):
        try:
            with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
                catalog = json.load(f)

            # Try to find the first module that isn't fully passed
            target_level = None
            target_video = None

            for lvl in catalog:
                lvl_title = lvl.get("level_title", "")
                # Check if quiz for this level is passed (completed_levels stores module_titles)
                if lvl_title in completed_levels:
                    continue  # skip: already cleared this module
                # This module is not yet cleared — find first unwatched video
                for v in lvl.get("videos", []):
                    if v.get("id", v.get("title", "")) not in watched_ids:
                        target_level = lvl
                        target_video = v
                        break
                if target_level:
                    break

            # If all done or no unwatched found, fall back to current level first video
            if not target_level:
                target_level = next(
                    (c for c in catalog if c.get("level_id") == current_level_id),
                    catalog[0] if catalog else None
                )
                target_video = target_level.get("videos", [{}])[0] if target_level else {}

            if target_level and target_video:
                return {
                    "level_title": target_level.get("level_title", "Module 1"),
                    "level_id": target_level.get("level_id", "level_1"),
                    "stage": target_level.get("stage", ""),
                    "title": target_video.get("title", ""),
                    "video_id": target_video.get("id", target_video.get("title", "")),
                    "creator": target_video.get("creator", "Zerodha Varsity"),
                    "duration": target_video.get("duration", "—"),
                    "xp": 50
                }
        except Exception:
            pass
    return {
        "level_title": "Module 1 — First ₹1,000",
        "level_id": "level_1",
        "stage": "Start Investing",
        "title": "What is Investing? Basics for Beginners",
        "video_id": "",
        "creator": "Zerodha Varsity",
        "duration": "8:15",
        "xp": 50
    }

def render(user_info):
    if "edu_test_state" not in st.session_state:
        st.session_state.edu_test_state = "dashboard" # 'dashboard', 'taking_test', 'test_failed', 'test_passed'
    if "active_quiz_module_id" not in st.session_state:
        st.session_state.active_quiz_module_id = "level_1"

    if st.session_state.edu_test_state == "taking_test":
        render_taking_test(user_info)
    elif st.session_state.edu_test_state == "test_failed":
        render_test_failed(user_info)
    elif st.session_state.edu_test_state == "test_passed":
        render_test_passed(user_info)
    else:
        render_dashboard(user_info)

def render_dashboard(user_info):
    progress = edu_db.load_progress()
    xp = progress.get("total_xp", 0)
    bal = float(progress.get("virtual_balance", 15000.0))
    invested = float(progress.get("invested_balance", 0.0))
    total_nw = bal + invested
    day_pnl = float(progress.get("daily_pnl", 0.0))
    day_pct = (day_pnl / total_nw * 100) if total_nw > 0 else 0.0

    # Real live data from edu_db
    watched_ids = progress.get("completed_articles", [])
    videos_watched = len(watched_ids)
    completed_levels = progress.get("completed_levels", [])  # list of module_titles passed

    # Dynamic level info from XP
    lvl_info = edu_db.get_level_info(xp)
    all_quizzes = _load_all_quizzes()

    # Smart hero: picks first uncompleted module + first unwatched video
    active_vid = _get_active_video_info(lvl_info["level_id"], completed_levels=completed_levels, watched_ids=watched_ids)
    # Active quiz follows the hero's video so they stay in sync
    hero_video_id = active_vid.get("video_id", "module_1_v1")
    active_quiz = all_quizzes.get(hero_video_id, list(all_quizzes.values())[0] if all_quizzes else {})
    questions_list = active_quiz.get("questions", [])
    q_count = len(questions_list)
    cash_reward = active_quiz.get("cash_reward", q_count * 50)
    xp_reward = active_quiz.get("xp_reward", 10)

    # Check if the current video's test has already been passed (ANTI-GLITCH)
    active_module_title = active_quiz.get("video_title", "")
    module_already_passed = active_module_title in completed_levels

    st.markdown("""
<style>
.dash-header-wrap { margin-bottom: 20px; }
.dash-header-title { font-size: 2.1rem; font-weight: 800; color: var(--q-text); letter-spacing: -0.5px; margin: 0 0 4px 0; }
.dash-header-sub { font-size: 1rem; color: var(--q-text-3); margin: 0; }

.edu-hero-card {
    background: linear-gradient(135deg, rgba(24, 28, 42, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
    border: 1px solid rgba(112, 126, 171, 0.28);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.35);
    position: relative;
    overflow: hidden;
}
.edu-hero-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; width: 4px; height: 100%;
    background: linear-gradient(180deg, #3b82f6 0%, #6366f1 100%);
}
.edu-hero-badge {
    background: rgba(59, 130, 246, 0.18);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.3);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    display: inline-block;
    margin-bottom: 10px;
}
.edu-hero-heading { font-size: 1.55rem; font-weight: 800; color: var(--q-text); margin: 0 0 6px 0; line-height: 1.3; }
.edu-hero-meta { font-size: 0.9rem; color: var(--q-text-3); display: flex; align-items: center; gap: 12px; }

.edu-port-card {
    background: linear-gradient(145deg, rgba(20,24,36,0.96), rgba(11,14,22,0.98));
    border: 1px solid rgba(112,126,171,0.24);
    border-radius: 16px;
    padding: 22px;
    box-shadow: 0 16px 36px rgba(0,0,0,0.25);
    margin-bottom: 24px;
}
.edu-port-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.edu-port-title { font-size: 0.95rem; font-weight: 700; color: var(--q-text-2); text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; }
.edu-port-val { font-size: 2.3rem; font-weight: 800; color: var(--q-text); font-family: 'JetBrains Mono', monospace; line-height: 1.1; margin-bottom: 4px; }
.edu-port-pnl { font-size: 0.92rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; margin-bottom: 18px; }
.edu-metrics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.08); }
.edu-metric-item { background: rgba(255,255,255,0.02); border: 1px solid rgba(112,126,171,0.15); border-radius: 10px; padding: 12px; }
.edu-metric-lbl { font-size: 0.72rem; color: var(--q-text-3); text-transform: uppercase; font-weight: 600; letter-spacing: 0.4px; margin-bottom: 4px; }
.edu-metric-num { font-size: 1.15rem; font-weight: 700; color: var(--q-text); font-family: 'JetBrains Mono', monospace; }

.q-section-title { font-size: 1.25rem; font-weight: 800; color: var(--q-text); margin: 0 0 16px 0; display: flex; align-items: center; justify-content: space-between; }
.q-news-card { display: flex; gap: 16px; background: rgba(20,24,36,0.95); border: 1px solid rgba(112,126,171,0.2); border-radius: 14px; padding: 14px; margin-bottom: 14px; transition: all 0.2s ease; }
.q-news-card:hover { border-color: rgba(129,140,248,0.45); transform: translateY(-1px); }
.q-news-img { width: 120px; height: 90px; border-radius: 10px; object-fit: cover; flex-shrink: 0; }
.q-news-body { flex: 1; min-width: 0; }
.q-news-pill { font-size: 0.65rem; font-weight: 700; color: #a5b4fc; background: rgba(99,102,241,0.15); padding: 2px 7px; border-radius: 4px; letter-spacing: 0.5px; display: inline-block; margin-bottom: 5px; }
.q-news-link { font-size: 0.95rem; font-weight: 700; color: var(--q-text); line-height: 1.35; margin: 0 0 5px; text-decoration: none; display: block; }
.q-news-link:hover { color: #818cf8; }
.q-news-snippet { font-size: 0.8rem; color: var(--q-text-2); line-height: 1.4; margin: 0 0 6px; }
.q-news-footer { display: flex; align-items: center; gap: 12px; font-size: 0.72rem; color: var(--q-text-3); }

.q-side-panel { background: linear-gradient(145deg, rgba(20,24,36,0.96), rgba(11,14,22,0.98)); border: 1px solid rgba(112,126,171,0.24); border-radius: 16px; padding: 16px; margin-bottom: 16px; }
.q-mini-index-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
.q-mini-index-box { background: rgba(255,255,255,0.02); border: 1px solid rgba(112,126,171,0.16); border-radius: 10px; padding: 10px; }
.q-trending-tag { display: inline-flex; align-items: center; gap: 4px; background: rgba(255,255,255,0.03); border: 1px solid rgba(112,126,171,0.2); border-radius: 8px; padding: 6px 10px; font-size: 0.78rem; font-weight: 600; color: var(--q-text); margin: 3px; }

/* Assessment Card & Level Progress Bar */
.edu-assignment-card {
    background: linear-gradient(135deg, rgba(99,102,241,0.14) 0%, rgba(168,85,247,0.14) 100%);
    border: 1px solid rgba(168,85,247,0.35);
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 16px;
}
.edu-asgn-badge {
    background: rgba(168,85,247,0.2);
    color: #c084fc;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 8px;
}
.edu-asgn-title { font-size: 1.15rem; font-weight: 800; color: var(--q-text); margin: 0 0 6px; }
.edu-asgn-sub { font-size: 0.82rem; color: var(--q-text-2); line-height: 1.4; margin-bottom: 12px; }
.edu-asgn-stats { display: flex; justify-content: space-between; font-size: 0.76rem; color: var(--q-text-3); font-weight: 600; margin-bottom: 10px; }
.edu-progress-bar-bg { width: 100%; height: 7px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; margin-bottom: 14px; }
.edu-progress-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6 0%, #a855f7 100%); border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

    _disp = user_info.get("display_name", "Student")
    st.markdown(textwrap.dedent(f"""
<div class="dash-header-wrap">
<h1 class="dash-header-title">Welcome back, {_disp} 👋</h1>
<p class="dash-header-sub">Your personal learning pathway and virtual investment command center.</p>
</div>
"""), unsafe_allow_html=True)

    # 1. Resume Journey Hero Banner
    hero_col_text, hero_col_btn = st.columns([3.2, 1.2], gap="medium")
    with hero_col_text:
        st.markdown(textwrap.dedent(f"""
<div class="edu-hero-card">
<div class="edu-hero-badge">Up Next &bull; {active_vid['level_title']}</div>
<h2 class="edu-hero-heading">{active_vid['title']}</h2>
<div class="edu-hero-meta">
<span>🎬 {active_vid['creator']}</span>
<span>⏱ {active_vid['duration']} mins</span>
<span style="color:#facc15;font-weight:700;">⭐ +{active_vid['xp']} XP Reward</span>
</div>
</div>
"""), unsafe_allow_html=True)

    with hero_col_btn:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        if st.button("▶ Resume Video in Library", key="btn_resume_hero", type="secondary", use_container_width=True):
            st.query_params["page"] = "Library"
            st.rerun()
        if module_already_passed:
            st.markdown("<div style='background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.35);border-radius:8px;padding:8px 12px;text-align:center;font-size:0.82rem;color:#10b981;font-weight:700;'>✅ Module Test Passed</div>", unsafe_allow_html=True)
        else:
            if st.button(f"📝 Start {active_quiz.get('video_title', 'Video')} Quiz", key="btn_hero_quiz", type="primary", use_container_width=True):
                st.session_state.active_quiz_module_id = hero_video_id
                st.session_state.edu_test_state = "taking_test"
                st.rerun()
        st.caption(f"Earn +{xp_reward} XP and unlock bonus trading cash.")

    # 2. Virtual Portfolio Snapshot
    pnl_color = "#10b981" if day_pnl >= 0 else "#ef4444"
    pnl_sign = "+" if day_pnl >= 0 else ""
    
    st.markdown(textwrap.dedent(f"""
<div class="edu-port-card">
<div class="edu-port-header">
<div class="edu-port-title">📈 Virtual Trading Sandbox &bull; Net Worth</div>
<span style="color:#10b981;font-size:0.75rem;font-weight:700;background:rgba(16,185,129,0.12);padding:3px 8px;border-radius:6px;">● Active Simulation</span>
</div>
<div class="edu-port-val">₹ {total_nw:,.2f}</div>
<div class="edu-port-pnl" style="color:{pnl_color};">{pnl_sign}₹{abs(day_pnl):,.2f} ({pnl_sign}{day_pct:.2f}%) Today</div>
<div class="edu-metrics-grid">
<div class="edu-metric-item">
<div class="edu-metric-lbl">Buying Power (Cash)</div>
<div class="edu-metric-num" style="color:#34d399;">₹ {bal:,.2f}</div>
</div>
<div class="edu-metric-item">
<div class="edu-metric-lbl">Videos Watched</div>
<div class="edu-metric-num" style="color:#60a5fa;">🎬 {videos_watched} / 100</div>
</div>
<div class="edu-metric-item">
<div class="edu-metric-lbl">Quizzes Passed</div>
<div class="edu-metric-num" style="color:#a855f7;">🏅 {len(completed_levels)} / 100</div>
</div>
</div>
<div style="display:flex;justify-content:space-between;font-size:0.74rem;color:var(--q-text-3);margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.08);">
<span>Total XP: <strong style="color:#facc15;">⭐ {xp:,} XP</strong></span>
<span>Level: <strong style="color:var(--q-text);">{lvl_info['level_name']}</strong></span>
</div>
</div>
"""), unsafe_allow_html=True)

    # 3. Market News Fall + Right Column (Indices, Trending Topics & Dynamic MCQ Assessment)
    st.markdown("<div class='q-section-title'><span>📰 Real-Time Market Intelligence</span><span style='font-size:0.8rem;color:var(--q-text-3);font-weight:500;'>Live Feed &bull; Auto-Refreshed</span></div>", unsafe_allow_html=True)

    col_articles, col_market_side = st.columns([1.7, 1.3], gap="large")

    with col_articles:
        try:
            live_news = news_sentiment.get_live_market_feed(limit_per_source=2)
        except Exception:
            live_news = []

        if live_news:
            for art in live_news[:4]:
                title = art.get("title", "Market Update")
                link = art.get("link", "#")
                summary = art.get("summary", "")
                cat = art.get("category", "MARKET UPDATE")
                img = art.get("image_url", "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&auto=format&fit=crop&q=80")
                read_time = art.get("read_time", "2 min read")
                dt_str = str(art.get("date", ""))[:10]
                ticker = art.get("ticker", "NSE")

                st.markdown(textwrap.dedent(f"""
<div class="q-news-card">
<img src="{img}" class="q-news-img" alt="{cat}">
<div class="q-news-body">
<span class="q-news-pill">{cat}</span>
<a href="{link}" target="_blank" class="q-news-link">{title}</a>
<p class="q-news-snippet">{summary[:115]}...</p>
<div class="q-news-footer">
<span>📅 {dt_str}</span>
<span>⏱ {read_time}</span>
<span>🏷 {ticker}</span>
</div>
</div>
</div>
"""), unsafe_allow_html=True)
        else:
            st.info("Market feed updating. Check back in a moment.")

    with col_market_side:
        # Market Overview Indices Card (NIFTY 50 + SENSEX)
        st.markdown(textwrap.dedent("""
<div class="q-side-panel">
<div style="font-size:0.85rem;font-weight:700;color:var(--q-text-2);text-transform:uppercase;margin-bottom:10px;">Market Overview</div>
<div class="q-mini-index-grid">
<div class="q-mini-index-box">
<div style="font-size:0.72rem;color:var(--q-text-3);font-weight:600;">NIFTY 50</div>
<div style="font-size:1.15rem;font-weight:800;color:var(--q-text);font-family:'JetBrains Mono',monospace;">24,080.40</div>
<div style="font-size:0.75rem;color:#ef4444;font-weight:700;">-95.25 (-0.39%) ↘</div>
</div>
<div class="q-mini-index-box">
<div style="font-size:0.72rem;color:var(--q-text-3);font-weight:600;">SENSEX</div>
<div style="font-size:1.15rem;font-weight:800;color:var(--q-text);font-family:'JetBrains Mono',monospace;">76,957.27</div>
<div style="font-size:0.75rem;color:#ef4444;font-weight:700;">-307.23 (-0.40%) ↘</div>
</div>
</div>
<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(112,126,171,0.16);border-radius:10px;padding:10px;display:flex;justify-content:space-around;text-align:center;">
<div>
<div style="font-size:0.68rem;color:var(--q-text-3);text-transform:uppercase;">Advances</div>
<div style="font-size:0.95rem;font-weight:800;color:#10b981;">1,243</div>
</div>
<div>
<div style="font-size:0.68rem;color:var(--q-text-3);text-transform:uppercase;">Declines</div>
<div style="font-size:0.95rem;font-weight:800;color:#ef4444;">678</div>
</div>
<div>
<div style="font-size:0.68rem;color:var(--q-text-3);text-transform:uppercase;">Status</div>
<div style="font-size:0.8rem;font-weight:700;color:#10b981;">● Open</div>
</div>
</div>
</div>
"""), unsafe_allow_html=True)

        # Trending Market Topics Card
        st.markdown(textwrap.dedent("""
<div class="q-side-panel">
<div style="font-size:0.85rem;font-weight:700;color:var(--q-text-2);text-transform:uppercase;margin-bottom:8px;">🔥 Trending Market Topics</div>
<div style="display:flex;flex-wrap:wrap;gap:6px;">
<span class="q-trending-tag">#NIFTY25K 🔥</span>
<span class="q-trending-tag">#Q2Results 📊</span>
<span class="q-trending-tag">#RBIPolicy 🏛️</span>
<span class="q-trending-tag">#AITechRally ⚡</span>
<span class="q-trending-tag">#TataSteel 🏭</span>
<span class="q-trending-tag">#GoldSilver 🪙</span>
</div>
</div>
"""), unsafe_allow_html=True)

        # Dynamic Assessment Card with Level Progress Bar
        nxt_txt = f"{lvl_info['next_xp']} XP" if lvl_info['next_xp'] else "MAX"
        passed_badge = "<div style='color:#10b981;font-size:0.8rem;font-weight:700;margin-bottom:8px;'>✅ Test Already Passed — Rewards Claimed</div>" if module_already_passed else ""
        card_border = "rgba(16,185,129,0.35)" if module_already_passed else "rgba(168,85,247,0.35)"
        card_bg = "rgba(16,185,129,0.1)" if module_already_passed else "rgba(99,102,241,0.14)"
        st.markdown(textwrap.dedent(f"""
<div style="background: linear-gradient(135deg, {card_bg} 0%, {card_bg} 100%); border: 1px solid {card_border}; border-radius: 16px; padding: 18px; margin-bottom: 16px;">
{passed_badge}
<div class="edu-asgn-badge">📝 Knowledge Evaluation Challenge</div>
<div class="edu-asgn-title">{active_quiz.get('video_title', 'Video')} Assessment</div>
<div class="edu-asgn-sub">{"Already completed. Select a different video below to continue earning." if module_already_passed else "Test your financial retention across this video to earn massive XP and unlock bonus trading capital."}</div>
<div class="edu-asgn-stats">
<span>🎯 {q_count} Questions</span>
<span>⚡ 85% to Pass</span>
<span style="color:#34d399;font-weight:700;">💰 ₹{cash_reward:,} Cash</span>
<span style="color:#facc15;font-weight:700;">⭐ +{xp_reward} XP</span>
</div>
<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:var(--q-text-3);margin-bottom:4px;">
<span>Level Progress: {xp:,} / {nxt_txt}</span>
<span>{lvl_info['progress_pct']:.0f}%</span>
</div>
<div class="edu-progress-bar-bg">
<div class="edu-progress-bar-fill" style="width: {lvl_info['progress_pct']}%;"></div>
</div>
</div>
"""), unsafe_allow_html=True)

        # Module Selector + Launch Button (with anti-glitch lock)
        quiz_options = {k: v.get("video_title", k) for k, v in all_quizzes.items()}
        # Mark passed ones with a checkmark in the dropdown
        def _fmt_quiz(k):
            title = quiz_options[k]
            all_q_data = all_quizzes.get(k, {})
            if all_q_data.get("video_title", "") in completed_levels:
                return f"✅ {title}"
            return title

        selected_mod_id = st.selectbox(
            "Select Video Assessment",
            options=list(quiz_options.keys()),
            format_func=_fmt_quiz,
            index=list(quiz_options.keys()).index(hero_video_id) if hero_video_id in quiz_options else 0,
            key="sel_quiz_mod"
        )
        st.session_state.active_quiz_module_id = selected_mod_id

        # Check if SELECTED module (not just active) has been passed
        selected_quiz_data = all_quizzes.get(selected_mod_id, {})
        selected_already_passed = selected_quiz_data.get("video_title", "") in completed_levels

        if selected_already_passed:
            st.success(f"✅ You already passed this module and claimed your rewards. Select an uncompleted module above.")
        else:
            if st.button(f"🚀 Launch {quiz_options[selected_mod_id]} Test", key="btn_start_quiz", type="primary", use_container_width=True):
                st.session_state.edu_test_state = "taking_test"
                st.rerun()

def render_taking_test(user_info):
    all_quizzes = _load_all_quizzes()
    mod_id = st.session_state.get("active_quiz_module_id", list(all_quizzes.keys())[0] if all_quizzes else "level_1")
    quiz_data = all_quizzes.get(mod_id, list(all_quizzes.values())[0] if all_quizzes else {})
    questions_list = quiz_data.get("questions", [])
    q_count = len(questions_list)
    cash_reward = quiz_data.get("cash_reward", q_count * 50)
    xp_reward = quiz_data.get("xp_reward", 10)

    st.markdown(textwrap.dedent(f"""
    <div style="margin-bottom: 20px;">
        <div style="font-size: 0.85rem; color: #a855f7; font-weight: 700; text-transform: uppercase;">{quiz_data.get('module_title', 'Education')} Challenge</div>
        <h1 style="font-size: 2rem; font-weight: 800; color: var(--q-text); margin: 0 0 6px 0;">📝 {quiz_data.get('video_title', 'Video')} Assessment</h1>
        <p style="color: var(--q-text-3); font-size: 1rem; margin: 0;">Answer all {q_count} questions. You must score <strong>at least 85%</strong> to earn <strong>+{xp_reward} XP</strong> and unlock <strong>₹{cash_reward:,} Virtual Trading Cash</strong>.</p>
    </div>
    <hr style="border-color: rgba(255,255,255,0.08); margin-bottom: 24px;">
    """), unsafe_allow_html=True)

    user_answers = {}
    
    with st.form("module_dynamic_quiz_form"):
        for idx, q in enumerate(questions_list):
            st.markdown(f"#### {q['question']}")
            ans = st.radio(
                label=f"q_{idx}",
                options=q["options"],
                index=None,
                key=f"mcq_ans_{mod_id}_{idx}",
                label_visibility="collapsed"
            )
            user_answers[idx] = ans
            st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 20px 0;'>", unsafe_allow_html=True)
        col_sub, col_cancel = st.columns([1.5, 1])
        with col_sub:
            submitted = st.form_submit_button("Submit Assessment & Grade", type="primary", use_container_width=True)
        with col_cancel:
            cancel = st.form_submit_button("Cancel & Return to Dashboard", use_container_width=True)

    if cancel:
        st.session_state.edu_test_state = "dashboard"
        st.rerun()

    if submitted:
        if any(user_answers[i] is None for i in range(q_count)):
            st.error(f"⚠️ Please answer all {q_count} questions before submitting!")
            return

        correct_count = 0
        detailed_results = []
        
        for idx, q in enumerate(questions_list):
            selected = user_answers[idx]
            is_correct = (selected == q["correct_answer"])
            if is_correct:
                correct_count += 1
            detailed_results.append({
                "question": q["question"],
                "selected": selected,
                "correct_answer": q["correct_answer"],
                "is_correct": is_correct,
                "explanation": q["explanation"]
            })

        score_pct = (correct_count / q_count) * 100
        st.session_state.quiz_score_pct = score_pct
        st.session_state.quiz_correct_count = correct_count
        st.session_state.quiz_total_count = q_count
        st.session_state.quiz_results = detailed_results
        st.session_state.quiz_video_title = quiz_data.get("video_title", "Video Assessment")
        st.session_state.quiz_cash_reward = cash_reward
        st.session_state.quiz_xp_reward = xp_reward

        if score_pct >= 85.0:
            # Passed!
            progress = edu_db.load_progress()
            progress["total_xp"] = progress.get("total_xp", 0) + xp_reward
            progress["virtual_balance"] = progress.get("virtual_balance", 15000.0) + float(cash_reward)
            
            comp_lvls = progress.get("completed_levels", [])
            vid_title = quiz_data.get("video_title", mod_id)
            if vid_title not in comp_lvls:
                comp_lvls.append(vid_title)
            progress["completed_levels"] = comp_lvls
            
            # Recalculate level automatically
            lvl_info = edu_db.get_level_info(progress["total_xp"])
            progress["current_level"] = lvl_info["level_name"]
            edu_db.save_progress(progress)
            
            st.session_state.edu_test_state = "test_passed"
            st.rerun()
        else:
            # Failed (< 85%)
            st.session_state.edu_test_state = "test_failed"
            st.rerun()

def render_test_passed(user_info):
    st.balloons()
    score = st.session_state.get("quiz_score_pct", 100)
    count = st.session_state.get("quiz_correct_count", 10)
    total = st.session_state.get("quiz_total_count", 10)
    vid_title = st.session_state.get("quiz_video_title", "Assessment")
    cash_reward = st.session_state.get("quiz_cash_reward", 500)
    xp_reward = st.session_state.get("quiz_xp_reward", 10)
    
    progress = edu_db.load_progress()
    lvl_info = edu_db.get_level_info(progress.get("total_xp", 0))

    st.markdown(textwrap.dedent(f"""
    <div style="background: linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(5,150,105,0.2) 100%); border: 1px solid rgba(16,185,129,0.4); border-radius: 20px; padding: 32px; text-align: center; margin: 30px 0;">
        <div style="font-size: 3.5rem; margin-bottom: 10px;">🏆</div>
        <h1 style="font-size: 2.3rem; font-weight: 900; color: #10b981; margin: 0 0 10px 0;">{vid_title} Mastered!</h1>
        <p style="font-size: 1.2rem; color: var(--q-text); margin-bottom: 20px;">Outstanding achievement! You scored <strong>{score:.0f}%</strong> ({count}/{total} correct), clearing the 85% passing threshold.</p>
        <div style="display: inline-flex; gap: 20px; background: rgba(0,0,0,0.3); padding: 14px 24px; border-radius: 12px; border: 1px solid rgba(16,185,129,0.3); margin-bottom: 24px;">
            <div style="font-size: 1.1rem; font-weight: 700; color: #facc15;">⭐ +{xp_reward} XP Earned</div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #34d399;">💰 +₹{cash_reward:,} Cash Deposited</div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #60a5fa;">🎖️ Rank: {lvl_info['level_name']}</div>
        </div>
    </div>
    """), unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("← Return to Dashboard", type="primary", use_container_width=True):
            st.session_state.edu_test_state = "dashboard"
            st.rerun()
    with col2:
        if st.button("📚 Continue Learning in Library", use_container_width=True):
            st.session_state.edu_test_state = "dashboard"
            st.query_params["page"] = "Library"
            st.rerun()

def render_test_failed(user_info):
    score = st.session_state.get("quiz_score_pct", 0)
    count = st.session_state.get("quiz_correct_count", 0)
    total = st.session_state.get("quiz_total_count", 10)
    results = st.session_state.get("quiz_results", [])
    vid_title = st.session_state.get("quiz_video_title", "Assessment")

    st.markdown(textwrap.dedent(f"""
    <div style="background: linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(185,28,28,0.2) 100%); border: 1px solid rgba(239,68,68,0.4); border-radius: 20px; padding: 28px; margin: 20px 0 30px 0;">
        <div>
            <div style="background: #ef4444; color: white; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 800; text-transform: uppercase; display: inline-block; margin-bottom: 8px;">Score: {score:.0f}% &bull; Minimum 85% Required to Pass</div>
            <h1 style="font-size: 2rem; font-weight: 900; color: var(--q-text); margin: 0 0 6px 0;">{vid_title} — Not Passed</h1>
            <p style="font-size: 1rem; color: var(--q-text-2); margin: 0;">You answered {count} out of {total} questions correctly ({score:.0f}%). Because passing requires at least 85%, no virtual cash was awarded for this attempt. Review the complete answer key and concept deep dives below before trying again.</p>
        </div>
    </div>
    """), unsafe_allow_html=True)

    st.markdown("## 🔍 Detailed Remediation & Answer Key")
    st.markdown("<p style='color: var(--q-text-3); font-size: 0.95rem;'>Review each financial concept thoroughly to understand the mechanics of the market.</p>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin-bottom: 20px;'>", unsafe_allow_html=True)

    for idx, r in enumerate(results):
        status_badge = "✅ Correct" if r["is_correct"] else "❌ Incorrect"
        badge_bg = "rgba(16,185,129,0.15)" if r["is_correct"] else "rgba(239,68,68,0.15)"
        badge_color = "#10b981" if r["is_correct"] else "#ef4444"
        card_border = "rgba(16,185,129,0.3)" if r["is_correct"] else "rgba(239,68,68,0.3)"

        st.markdown(textwrap.dedent(f"""
<div style="background: rgba(20,24,36,0.95); border: 1px solid {card_border}; border-radius: 14px; padding: 18px 20px; margin-bottom: 18px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
<span style="font-size:0.85rem; font-weight:700; color:var(--q-text-2);">Question {idx+1}</span>
<span style="font-size:0.75rem; font-weight:800; background:{badge_bg}; color:{badge_color}; padding:3px 8px; border-radius:6px;">{status_badge}</span>
</div>
<h3 style="font-size:1.1rem; font-weight:700; color:var(--q-text); margin:0 0 12px 0;">{r['question']}</h3>
<div style="margin-bottom:8px; font-size:0.9rem;">
<span style="color:var(--q-text-3);">Your Selection:</span> <strong style="color:{badge_color};">{r['selected']}</strong>
</div>
<div style="margin-bottom:12px; font-size:0.9rem;">
<span style="color:var(--q-text-3);">Correct Answer:</span> <strong style="color:#10b981;">{r['correct_answer']}</strong>
</div>
<div style="background:rgba(255,255,255,0.03); border-left:3px solid #3b82f6; border-radius:4px; padding:10px 14px;">
<div style="font-size:0.75rem; font-weight:700; color:#60a5fa; text-transform:uppercase; margin-bottom:4px;">💡 What this is about (Concept Deep Dive)</div>
<div style="font-size:0.85rem; color:var(--q-text-2); line-height:1.45;">{r['explanation']}</div>
</div>
</div>
"""), unsafe_allow_html=True)

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 24px 0;'>", unsafe_allow_html=True)
    
    btn_col1, btn_col2 = st.columns([1.2, 1.2])
    with btn_col1:
        if st.button("🔄 Re-attempt Assessment", type="primary", use_container_width=True):
            st.session_state.edu_test_state = "taking_test"
            st.rerun()
    with btn_col2:
        if st.button("📚 Study Topics in Knowledge Library", use_container_width=True):
            st.session_state.edu_test_state = "dashboard"
            st.query_params["page"] = "Library"
            st.rerun()
