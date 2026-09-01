import streamlit as st
import textwrap
import json
import os
import re
import edu_db
import news_sentiment
import nse_live as _nse

_HERE = os.path.dirname(os.path.abspath(__file__))
_CATALOG_PATH = os.path.join(os.path.dirname(_HERE), "education_catalog.json")
_QUIZZES_PATH = os.path.join(os.path.dirname(_HERE), "education_video_quizzes.json")

# ─── Module icon map ──────────────────────────────────────────────────
_MODULE_ICONS = {
    1: "💰", 2: "📈", 3: "🎯", 4: "🎨", 5: "🏗️",
    6: "🤔", 7: "🔍", 8: "📊", 9: "⛈️", 10: "🏆",
}

# ─── Helpers ──────────────────────────────────────────────────────────

def _load_all_quizzes():
    if os.path.exists(_QUIZZES_PATH):
        try:
            with open(_QUIZZES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _extract_video_num(key):
    """module_1_v3 -> 3"""
    m = re.search(r'_v(\d+)$', key)
    return int(m.group(1)) if m else 0


def _extract_module_num(prefix):
    """module_3 -> 3, module_tax -> 10"""
    if "tax" in prefix.lower():
        return 10
    m = re.search(r'module_(\d+)', prefix)
    return int(m.group(1)) if m else 99


def _get_module_prefix(key):
    """module_1_v3 -> module_1"""
    parts = key.rsplit('_v', 1)
    return parts[0] if len(parts) == 2 else key


def _get_module_groups(all_quizzes):
    """Group quizzes by module prefix.  Returns an ordered list of dicts."""
    groups = {}
    for key, quiz in all_quizzes.items():
        prefix = _get_module_prefix(key)
        if prefix not in groups:
            groups[prefix] = {
                "prefix": prefix,
                "module_title": quiz.get("module_title", "Unknown"),
                "module_id": quiz.get("module_id", ""),
                "keys": [],
            }
        groups[prefix]["keys"].append(key)

    for g in groups.values():
        g["keys"].sort(key=_extract_video_num)

    return sorted(groups.values(), key=lambda g: _extract_module_num(g["prefix"]))


def _get_quiz_statuses(quiz_keys, all_quizzes, completed_levels):
    """Returns a list of status dicts for each quiz key — in order.

    Status is one of: 'passed', 'available', 'locked'.
    Video 1 is always available; Video N requires Video N-1 to be passed.
    """
    statuses = []
    prev_passed = True  # first quiz is always available
    for key in quiz_keys:
        quiz = all_quizzes.get(key, {})
        video_title = quiz.get("video_title", "")
        is_passed = video_title in completed_levels
        if is_passed:
            status = "passed"
        elif prev_passed:
            status = "available"
        else:
            status = "locked"
        statuses.append({
            "key": key,
            "video_title": video_title,
            "status": status,
            "quiz": quiz,
        })
        prev_passed = is_passed
    return statuses


def _get_active_video_info(current_level_id="level_1", completed_levels=None, watched_ids=None):
    """Returns the hero 'Up Next' info (best-effort from catalog)."""
    completed_levels = completed_levels or []
    watched_ids = set(watched_ids or [])

    if os.path.exists(_CATALOG_PATH):
        try:
            with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            target_level = None
            target_video = None
            for lvl in catalog:
                lvl_title = lvl.get("level_title", "")
                if lvl_title in completed_levels:
                    continue
                for v in lvl.get("videos", lvl.get("topics", [])):
                    vid_id = v.get("id", v.get("topic", ""))
                    if vid_id not in watched_ids:
                        target_level = lvl
                        target_video = v
                        break
                if target_level:
                    break
            if not target_level:
                target_level = next(
                    (c for c in catalog if c.get("level_id") == current_level_id),
                    catalog[0] if catalog else None,
                )
                vids = target_level.get("videos", target_level.get("topics", [{}])) if target_level else [{}]
                target_video = vids[0] if vids else {}
            if target_level and target_video:
                return {
                    "level_title": target_level.get("level_title", "Module 1"),
                    "level_id": target_level.get("level_id", "level_1"),
                    "stage": target_level.get("stage", ""),
                    "title": target_video.get("topic", target_video.get("title", "")),
                    "video_id": target_video.get("id", target_video.get("topic", "")),
                    "creator": target_video.get("creator", "Zerodha Varsity"),
                    "duration": target_video.get("duration", "—"),
                    "xp": 50,
                }
        except Exception:
            pass
    return {
        "level_title": "Module 1 — First ₹1,000",
        "level_id": "module_1",
        "stage": "Start Investing",
        "title": "What is Investing? Basics for Beginners",
        "video_id": "",
        "creator": "Zerodha Varsity",
        "duration": "8:15",
        "xp": 50,
    }


# ─── State Router ─────────────────────────────────────────────────────

def render(user_info):
    if "edu_test_state" not in st.session_state:
        st.session_state.edu_test_state = "dashboard"
    if "active_quiz_module_id" not in st.session_state:
        st.session_state.active_quiz_module_id = "module_1_v1"
    if "active_module_id" not in st.session_state:
        st.session_state.active_module_id = None

    state = st.session_state.edu_test_state
    if state == "module_hub":
        render_module_hub(user_info)
    elif state == "taking_test":
        render_taking_test(user_info)
    elif state == "test_passed":
        render_test_passed(user_info)
    elif state == "test_failed":
        render_test_failed(user_info)
    elif state == "review":
        render_review(user_info)
    else:
        render_dashboard(user_info)


# ─── Dashboard ────────────────────────────────────────────────────────

def render_dashboard(user_info):
    progress = edu_db.load_progress()
    xp = progress.get("total_xp", 0)
    bal = float(progress.get("virtual_balance", 15000.0))
    invested = float(progress.get("invested_balance", 0.0))
    total_nw = bal + invested
    day_pnl = float(progress.get("daily_pnl", 0.0))
    day_pct = (day_pnl / total_nw * 100) if total_nw > 0 else 0.0

    watched_ids = progress.get("completed_articles", [])
    videos_watched = len(watched_ids)
    completed_levels = progress.get("completed_levels", [])

    lvl_info = edu_db.get_level_info(xp)
    all_quizzes = _load_all_quizzes()
    module_groups = _get_module_groups(all_quizzes)

    # Count quizzes passed + modules fully cleared
    quizzes_passed = len(completed_levels)
    modules_cleared = 0
    for grp in module_groups:
        sts = _get_quiz_statuses(grp["keys"], all_quizzes, completed_levels)
        if all(s["status"] == "passed" for s in sts):
            modules_cleared += 1

    # Hero: find first uncompleted module
    hero_module = None
    hero_next_quiz = None
    for grp in module_groups:
        sts = _get_quiz_statuses(grp["keys"], all_quizzes, completed_levels)
        passed_count = sum(1 for s in sts if s["status"] == "passed")
        if passed_count < len(sts):
            hero_module = grp
            hero_next_quiz = next((s for s in sts if s["status"] == "available"), None)
            break
    if not hero_module and module_groups:
        hero_module = module_groups[0]

    hero_title = hero_next_quiz["video_title"] if hero_next_quiz else (hero_module["module_title"] if hero_module else "All Complete!")
    hero_mod_title = hero_module["module_title"] if hero_module else "All Modules"
    hero_prefix = hero_module["prefix"] if hero_module else "module_1"

    # ── CSS ──────────────────────────────────────────────────────
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

/* Module Cards Grid */
.mod-card {
    background: linear-gradient(145deg, rgba(20,24,36,0.96), rgba(11,14,22,0.98));
    border: 1px solid rgba(112,126,171,0.24);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 6px;
    transition: all 0.2s ease;
}
.mod-card:hover { border-color: rgba(129,140,248,0.4); transform: translateY(-2px); }
.mod-card-complete {
    background: linear-gradient(145deg, rgba(16,185,129,0.08), rgba(5,150,105,0.06));
    border-color: rgba(16,185,129,0.35);
}
.mod-card-icon { font-size: 1.6rem; margin-bottom: 6px; }
.mod-card-title { font-size: 0.95rem; font-weight: 700; color: var(--q-text); margin-bottom: 4px; line-height: 1.3; }
.mod-card-progress { font-size: 0.78rem; color: var(--q-text-3); font-weight: 600; margin-bottom: 8px; }
.mod-card-bar-bg { width: 100%; height: 5px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden; }
.mod-card-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s ease; }

.edu-progress-bar-bg { width: 100%; height: 7px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; margin-bottom: 14px; }
.edu-progress-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6 0%, #a855f7 100%); border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

    # ── Header ───────────────────────────────────────────────────
    _disp = user_info.get("display_name", "Student")
    st.markdown(textwrap.dedent(f"""
<div class="dash-header-wrap">
<h1 class="dash-header-title">Welcome back, {_disp} 👋</h1>
<p class="dash-header-sub">Your personal learning pathway and virtual investment command center.</p>
</div>
"""), unsafe_allow_html=True)

    # ── Hero Banner ──────────────────────────────────────────────
    hero_col_text, hero_col_btn = st.columns([3.2, 1.2], gap="medium")
    with hero_col_text:
        st.markdown(textwrap.dedent(f"""
<div class="edu-hero-card">
<div class="edu-hero-badge">Up Next &bull; {hero_mod_title}</div>
<h2 class="edu-hero-heading">{hero_title}</h2>
<div class="edu-hero-meta">
<span>📋 {hero_mod_title}</span>
<span style="color:#facc15;font-weight:700;">⭐ +10 XP per Quiz</span>
</div>
</div>
"""), unsafe_allow_html=True)

    with hero_col_btn:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        if st.button("▶ Resume Video in Library", key="btn_resume_hero", type="secondary", use_container_width=True):
            st.query_params["page"] = "Library"
            st.rerun()
        if st.button(f"📋 View {hero_mod_title.split('—')[0].strip()} Quizzes", key="btn_hero_mod_hub", type="primary", use_container_width=True):
            st.session_state.active_module_id = hero_prefix
            st.session_state.edu_test_state = "module_hub"
            st.rerun()
        st.caption("Pass video quizzes to earn XP and unlock trading cash.")

    # ── Portfolio Snapshot ────────────────────────────────────────
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
<div class="edu-metric-num" style="color:#a855f7;">🏅 {quizzes_passed} / 100</div>
</div>
</div>
<div style="display:flex;justify-content:space-between;font-size:0.74rem;color:var(--q-text-3);margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.08);">
<span>Total XP: <strong style="color:#facc15;">⭐ {xp:,} XP</strong></span>
<span>Modules Cleared: <strong style="color:#a855f7;">{modules_cleared} / 10</strong></span>
<span>Level: <strong style="color:var(--q-text);">{lvl_info['level_name']}</strong></span>
</div>
</div>
"""), unsafe_allow_html=True)

    # ── Module Assessment Cards ──────────────────────────────────
    st.markdown("<div class='q-section-title'><span>📝 Module Assessments</span><span style='font-size:0.8rem;color:var(--q-text-3);font-weight:500;'>10 Modules &bull; 100 Video Quizzes</span></div>", unsafe_allow_html=True)

    cols = st.columns(2, gap="medium")
    for i, grp in enumerate(module_groups):
        sts = _get_quiz_statuses(grp["keys"], all_quizzes, completed_levels)
        passed = sum(1 for s in sts if s["status"] == "passed")
        total = len(sts)
        is_complete = (passed == total)
        mod_num = _extract_module_num(grp["prefix"])
        icon = _MODULE_ICONS.get(mod_num, "📚")
        pct = (passed / total * 100) if total > 0 else 0
        bar_color = "linear-gradient(90deg, #10b981 0%, #34d399 100%)" if is_complete else "linear-gradient(90deg, #3b82f6 0%, #a855f7 100%)"
        card_cls = "mod-card mod-card-complete" if is_complete else "mod-card"
        complete_badge = "<span style='color:#10b981;font-size:0.7rem;font-weight:800;'>✅ COMPLETE</span>" if is_complete else ""

        with cols[i % 2]:
            st.markdown(textwrap.dedent(f"""
<div class="{card_cls}">
<div style="display:flex;justify-content:space-between;align-items:center;">
<div class="mod-card-icon">{icon}</div>
{complete_badge}
</div>
<div class="mod-card-title">{grp['module_title']}</div>
<div class="mod-card-progress">{passed}/{total} Quizzes Passed</div>
<div class="mod-card-bar-bg">
<div class="mod-card-bar-fill" style="width:{pct:.0f}%;background:{bar_color};"></div>
</div>
</div>
"""), unsafe_allow_html=True)
            if st.button(f"View Quizzes →", key=f"mod_btn_{grp['prefix']}", use_container_width=True):
                st.session_state.active_module_id = grp["prefix"]
                st.session_state.edu_test_state = "module_hub"
                st.rerun()

    # ── Market News + Sidebar ────────────────────────────────────
    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
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
        # Market Overview Indices Card
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

        # Trending Market Topics
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

        # Level Progress Card (compact)
        nxt_txt = f"{lvl_info['next_xp']} XP" if lvl_info['next_xp'] else "MAX"
        st.markdown(textwrap.dedent(f"""
<div class="q-side-panel">
<div style="font-size:0.85rem;font-weight:700;color:var(--q-text-2);text-transform:uppercase;margin-bottom:8px;">🎖️ Level Progress</div>
<div style="font-size:1.1rem;font-weight:800;color:var(--q-text);margin-bottom:6px;">{lvl_info['level_name']}</div>
<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:var(--q-text-3);margin-bottom:4px;">
<span>{xp:,} / {nxt_txt}</span>
<span>{lvl_info['progress_pct']:.0f}%</span>
</div>
<div class="edu-progress-bar-bg">
<div class="edu-progress-bar-fill" style="width: {lvl_info['progress_pct']}%;"></div>
</div>
</div>
"""), unsafe_allow_html=True)


# ─── Module Quiz Hub ──────────────────────────────────────────────────

def render_module_hub(user_info):
    all_quizzes = _load_all_quizzes()
    module_groups = _get_module_groups(all_quizzes)
    completed_levels = edu_db.load_progress().get("completed_levels", [])

    prefix = st.session_state.get("active_module_id", "module_1")
    grp = next((g for g in module_groups if g["prefix"] == prefix), None)
    if not grp:
        st.session_state.edu_test_state = "dashboard"
        st.rerun()
        return

    statuses = _get_quiz_statuses(grp["keys"], all_quizzes, completed_levels)
    passed = sum(1 for s in statuses if s["status"] == "passed")
    total = len(statuses)
    mod_num = _extract_module_num(prefix)
    icon = _MODULE_ICONS.get(mod_num, "📚")
    pct = (passed / total * 100) if total > 0 else 0
    all_complete = (passed == total)

    st.markdown("""
<style>
.hub-card {
    background: linear-gradient(145deg, rgba(20,24,36,0.96), rgba(11,14,22,0.98));
    border: 1px solid rgba(112,126,171,0.24);
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 8px;
    transition: all 0.2s ease;
}
.hub-card:hover { border-color: rgba(129,140,248,0.4); }
.hub-card-locked {
    background: rgba(20,24,36,0.6);
    border-color: rgba(112,126,171,0.12);
    opacity: 0.6;
}
.hub-card-passed {
    background: linear-gradient(145deg, rgba(16,185,129,0.08), rgba(5,150,105,0.06));
    border-color: rgba(16,185,129,0.35);
}
.hub-card-available {
    border-color: rgba(168,85,247,0.45);
    box-shadow: 0 0 16px rgba(168,85,247,0.12);
}
.hub-status-pill {
    font-size: 0.72rem;
    font-weight: 800;
    padding: 3px 10px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}
</style>
""", unsafe_allow_html=True)

    # Back button
    if st.button("← Back to Dashboard", key="btn_hub_back"):
        st.session_state.edu_test_state = "dashboard"
        st.rerun()

    # Header
    complete_badge = " &nbsp;<span style='color:#10b981;font-size:0.9rem;'>✅ All Complete!</span>" if all_complete else ""
    st.markdown(textwrap.dedent(f"""
<div style="margin-bottom: 24px;">
<div style="font-size:2.5rem;margin-bottom:6px;">{icon}</div>
<h1 style="font-size:2rem;font-weight:900;color:var(--q-text);margin:0 0 6px 0;">{grp['module_title']}{complete_badge}</h1>
<p style="color:var(--q-text-3);font-size:1rem;margin:0 0 12px 0;">Complete each video quiz sequentially. Pass with <strong>85%</strong> to unlock the next.</p>
<div style="display:flex;gap:16px;align-items:center;">
<span style="font-size:0.85rem;font-weight:700;color:var(--q-text-2);">{passed}/{total} Quizzes Passed</span>
<div style="flex:1;height:6px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden;max-width:300px;">
<div style="width:{pct:.0f}%;height:100%;background:linear-gradient(90deg,#3b82f6,#a855f7);border-radius:3px;"></div>
</div>
<span style="font-size:0.78rem;color:var(--q-text-3);">{pct:.0f}%</span>
</div>
</div>
<hr style="border-color:rgba(255,255,255,0.08);margin-bottom:20px;">
"""), unsafe_allow_html=True)

    # Quiz Cards
    for idx, qs in enumerate(statuses):
        vid_num = idx + 1
        status = qs["status"]
        title = qs["video_title"]
        key = qs["key"]
        quiz = qs["quiz"]
        q_count = len(quiz.get("questions", []))
        xp_reward = quiz.get("xp_reward", 10)
        cash_reward = quiz.get("cash_reward", 50)

        if status == "passed":
            card_cls = "hub-card hub-card-passed"
            status_html = "<span class='hub-status-pill' style='background:rgba(16,185,129,0.15);color:#10b981;'>✅ Passed</span>"
        elif status == "available":
            card_cls = "hub-card hub-card-available"
            status_html = "<span class='hub-status-pill' style='background:rgba(168,85,247,0.15);color:#c084fc;'>🔓 Available</span>"
        else:
            card_cls = "hub-card hub-card-locked"
            status_html = "<span class='hub-status-pill' style='background:rgba(255,255,255,0.05);color:var(--q-text-3);'>🔒 Locked</span>"

        st.markdown(textwrap.dedent(f"""
<div class="{card_cls}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
<div style="display:flex;align-items:center;gap:10px;">
<span style="font-size:1.3rem;font-weight:900;color:var(--q-text-2);">#{vid_num}</span>
<span style="font-size:1rem;font-weight:700;color:var(--q-text);">{title}</span>
</div>
{status_html}
</div>
<div style="display:flex;gap:16px;font-size:0.78rem;color:var(--q-text-3);">
<span>🎯 {q_count} Questions</span>
<span>⚡ 85% to Pass</span>
<span style="color:#facc15;font-weight:600;">⭐ +{xp_reward} XP</span>
<span style="color:#34d399;font-weight:600;">💰 +₹{cash_reward:,}</span>
</div>
</div>
"""), unsafe_allow_html=True)

        if status == "available":
            if st.button(f"🚀 Start Quiz — {title}", key=f"start_{key}", type="primary", use_container_width=True):
                st.session_state.active_quiz_module_id = key
                st.session_state.edu_test_state = "taking_test"
                st.rerun()
        elif status == "locked":
            st.caption("🔒 Complete the previous quiz to unlock this one.")

    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)


# ─── Taking Test ──────────────────────────────────────────────────────

def render_taking_test(user_info):
    all_quizzes = _load_all_quizzes()
    mod_id = st.session_state.get("active_quiz_module_id", list(all_quizzes.keys())[0] if all_quizzes else "module_1_v1")
    quiz_data = all_quizzes.get(mod_id, list(all_quizzes.values())[0] if all_quizzes else {})
    questions_list = quiz_data.get("questions", [])
    q_count = len(questions_list)
    cash_reward = quiz_data.get("cash_reward", 50)
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
            # Use 'q' key (JSON field) for question text
            question_text = q.get("q", q.get("question", f"Question {idx+1}"))
            st.markdown(f"#### {question_text}")
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
            cancel = st.form_submit_button("Cancel & Return", use_container_width=True)

    if cancel:
        st.session_state.edu_test_state = "module_hub"
        st.rerun()

    if submitted:
        if any(user_answers[i] is None for i in range(q_count)):
            st.error(f"⚠️ Please answer all {q_count} questions before submitting!")
            return

        correct_count = 0
        detailed_results = []

        for idx, q in enumerate(questions_list):
            selected = user_answers[idx]
            # Correct answer: use integer index from 'answer' key to get option text
            correct_idx = q.get("answer", 0)
            correct_text = q["options"][correct_idx] if correct_idx < len(q["options"]) else q["options"][0]
            is_correct = (selected == correct_text)
            if is_correct:
                correct_count += 1
            # Explanation: use 'concept' key
            explanation = q.get("concept", q.get("explanation", ""))
            question_text = q.get("q", q.get("question", f"Question {idx+1}"))
            detailed_results.append({
                "question": question_text,
                "selected": selected,
                "correct_answer": correct_text,
                "is_correct": is_correct,
                "explanation": explanation,
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

            lvl_info = edu_db.get_level_info(progress["total_xp"])
            progress["current_level"] = lvl_info["level_name"]
            edu_db.save_progress(progress)

            st.session_state.edu_test_state = "test_passed"
            st.rerun()
        else:
            st.session_state.edu_test_state = "test_failed"
            st.rerun()


# ─── Test Passed — Celebration ────────────────────────────────────────

def render_test_passed(user_info):
    st.balloons()
    score = st.session_state.get("quiz_score_pct", 100)
    count = st.session_state.get("quiz_correct_count", 10)
    total = st.session_state.get("quiz_total_count", 10)
    vid_title = st.session_state.get("quiz_video_title", "Assessment")
    cash_reward = st.session_state.get("quiz_cash_reward", 50)
    xp_reward = st.session_state.get("quiz_xp_reward", 10)

    progress = edu_db.load_progress()
    lvl_info = edu_db.get_level_info(progress.get("total_xp", 0))

    # Confetti particles
    confetti_colors = ["#3b82f6", "#a855f7", "#10b981", "#facc15", "#ef4444", "#f97316", "#ec4899", "#06b6d4"]
    confetti_html = ""
    for i in range(30):
        color = confetti_colors[i % len(confetti_colors)]
        left = (i * 3.3) % 100
        delay = (i * 0.12) % 2.5
        size = 8 + (i % 5) * 2
        confetti_html += f'<div style="position:fixed;left:{left}%;top:-20px;width:{size}px;height:{size}px;background:{color};border-radius:{2 if i%2==0 else 50}%;animation:confetti-fall {2.5 + delay}s ease-in {delay}s forwards;z-index:9999;opacity:0.9;"></div>\n'

    st.markdown(f"""
<style>
@keyframes confetti-fall {{
    0% {{ transform: translateY(-10vh) rotate(0deg); opacity: 1; }}
    100% {{ transform: translateY(110vh) rotate(720deg); opacity: 0; }}
}}
@keyframes trophy-bounce {{
    0% {{ transform: scale(0) rotate(-20deg); opacity: 0; }}
    40% {{ transform: scale(1.35) rotate(5deg); opacity: 1; }}
    60% {{ transform: scale(0.9) rotate(-3deg); }}
    80% {{ transform: scale(1.05) rotate(1deg); }}
    100% {{ transform: scale(1) rotate(0deg); opacity: 1; }}
}}
@keyframes slide-up {{
    0% {{ transform: translateY(30px); opacity: 0; }}
    100% {{ transform: translateY(0); opacity: 1; }}
}}
@keyframes glow-pulse {{
    0%, 100% {{ box-shadow: 0 0 20px rgba(16,185,129,0.3); }}
    50% {{ box-shadow: 0 0 40px rgba(16,185,129,0.6); }}
}}
</style>
{confetti_html}
""", unsafe_allow_html=True)

    st.markdown(textwrap.dedent(f"""
<div style="background: linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(5,150,105,0.2) 100%); border: 2px solid rgba(16,185,129,0.5); border-radius: 24px; padding: 40px; text-align: center; margin: 20px 0; animation: glow-pulse 2s ease-in-out infinite;">
    <div style="font-size: 5rem; margin-bottom: 14px; animation: trophy-bounce 1s ease-out forwards;">🏆</div>
    <h1 style="font-size: 2.5rem; font-weight: 900; color: #10b981; margin: 0 0 8px 0; animation: slide-up 0.6s ease-out 0.3s both;">Assessment Mastered!</h1>
    <p style="font-size: 1.15rem; color: var(--q-text-2); margin-bottom: 8px; animation: slide-up 0.6s ease-out 0.5s both;">{vid_title}</p>
    <p style="font-size: 1.3rem; color: var(--q-text); margin-bottom: 24px; animation: slide-up 0.6s ease-out 0.7s both;">You scored <strong style="color:#10b981;">{score:.0f}%</strong> ({count}/{total} correct) — well above the 85% passing threshold!</p>
    <div style="display: inline-flex; gap: 16px; flex-wrap: wrap; justify-content: center; animation: slide-up 0.8s ease-out 0.9s both;">
        <div style="background: rgba(250,204,21,0.12); border: 1px solid rgba(250,204,21,0.35); padding: 12px 20px; border-radius: 12px;">
            <div style="font-size: 1.3rem; font-weight: 800; color: #facc15;">⭐ +{xp_reward} XP</div>
            <div style="font-size: 0.72rem; color: var(--q-text-3); margin-top: 2px;">Experience Earned</div>
        </div>
        <div style="background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.35); padding: 12px 20px; border-radius: 12px;">
            <div style="font-size: 1.3rem; font-weight: 800; color: #34d399;">💰 +₹{cash_reward:,}</div>
            <div style="font-size: 0.72rem; color: var(--q-text-3); margin-top: 2px;">Cash Deposited</div>
        </div>
        <div style="background: rgba(96,165,250,0.12); border: 1px solid rgba(96,165,250,0.35); padding: 12px 20px; border-radius: 12px;">
            <div style="font-size: 1.3rem; font-weight: 800; color: #60a5fa;">🎖️ {lvl_info['level_name']}</div>
            <div style="font-size: 0.72rem; color: var(--q-text-3); margin-top: 2px;">Current Rank</div>
        </div>
    </div>
</div>
"""), unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("📖 View Detailed Results", type="primary", use_container_width=True):
            st.session_state.edu_test_state = "review"
            st.rerun()
    with col2:
        if st.button("← Back to Module", use_container_width=True):
            st.session_state.edu_test_state = "module_hub"
            st.rerun()
    with col3:
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.edu_test_state = "dashboard"
            st.rerun()


# ─── Test Failed ──────────────────────────────────────────────────────

def render_test_failed(user_info):
    score = st.session_state.get("quiz_score_pct", 0)
    count = st.session_state.get("quiz_correct_count", 0)
    total = st.session_state.get("quiz_total_count", 10)
    vid_title = st.session_state.get("quiz_video_title", "Assessment")

    st.markdown("""
<style>
@keyframes shake-card {
    0%, 100% { transform: translateX(0); }
    10%, 30%, 50%, 70%, 90% { transform: translateX(-6px); }
    20%, 40%, 60%, 80% { transform: translateX(6px); }
}
@keyframes fade-in-up {
    0% { transform: translateY(20px); opacity: 0; }
    100% { transform: translateY(0); opacity: 1; }
}
</style>
""", unsafe_allow_html=True)

    st.markdown(textwrap.dedent(f"""
<div style="background: linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(185,28,28,0.2) 100%); border: 2px solid rgba(239,68,68,0.5); border-radius: 24px; padding: 36px; text-align: center; margin: 20px 0; animation: shake-card 0.6s ease-in-out;">
    <div style="font-size: 4.5rem; margin-bottom: 14px;">😔</div>
    <h1 style="font-size: 2.3rem; font-weight: 900; color: var(--q-text); margin: 0 0 8px 0;">Not Quite There Yet</h1>
    <p style="font-size: 1.15rem; color: var(--q-text-2); margin-bottom: 6px;">{vid_title}</p>
    <div style="display: inline-flex; gap: 12px; align-items: center; margin-bottom: 16px;">
        <span style="background: #ef4444; color: white; padding: 6px 14px; border-radius: 8px; font-size: 1.2rem; font-weight: 900;">{score:.0f}%</span>
        <span style="color: var(--q-text-3); font-size: 1rem;">You needed <strong style="color:#facc15;">85%</strong> to pass</span>
    </div>
    <p style="font-size: 1rem; color: var(--q-text-2); margin: 0;">You answered {count} out of {total} correctly. Review your mistakes below and try again — you've got this! 💪</p>
</div>
"""), unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🔍 View Your Mistakes", type="primary", use_container_width=True):
            st.session_state.edu_test_state = "review"
            st.rerun()
    with col2:
        if st.button("🔄 Re-attempt Now", use_container_width=True):
            st.session_state.edu_test_state = "taking_test"
            st.rerun()
    with col3:
        if st.button("📚 Study in Library", use_container_width=True):
            st.session_state.edu_test_state = "dashboard"
            st.query_params["page"] = "Library"
            st.rerun()


# ─── Review Page ──────────────────────────────────────────────────────

def render_review(user_info):
    score = st.session_state.get("quiz_score_pct", 0)
    count = st.session_state.get("quiz_correct_count", 0)
    total = st.session_state.get("quiz_total_count", 10)
    results = st.session_state.get("quiz_results", [])
    vid_title = st.session_state.get("quiz_video_title", "Assessment")
    passed = score >= 85.0

    result_color = "#10b981" if passed else "#ef4444"
    result_label = "PASSED" if passed else "NOT PASSED"

    st.markdown(textwrap.dedent(f"""
<div style="margin-bottom: 24px;">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
    <span style="background:{result_color};color:white;padding:4px 12px;border-radius:6px;font-size:0.78rem;font-weight:800;text-transform:uppercase;">{result_label} — {score:.0f}%</span>
    <span style="font-size:0.9rem;color:var(--q-text-3);">{count}/{total} Correct</span>
</div>
<h1 style="font-size:2rem;font-weight:800;color:var(--q-text);margin:0 0 6px 0;">📖 {vid_title} — Answer Review</h1>
<p style="color:var(--q-text-3);font-size:1rem;margin:0;">Review each question, your answer, the correct answer, and the concept explanation.</p>
</div>
<hr style="border-color:rgba(255,255,255,0.08);margin-bottom:24px;">
"""), unsafe_allow_html=True)

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
<div style="font-size:0.75rem; font-weight:700; color:#60a5fa; text-transform:uppercase; margin-bottom:4px;">💡 Concept Deep Dive</div>
<div style="font-size:0.85rem; color:var(--q-text-2); line-height:1.45;">{r['explanation']}</div>
</div>
</div>
"""), unsafe_allow_html=True)

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 24px 0;'>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← Back to Module", type="primary", use_container_width=True):
            st.session_state.edu_test_state = "module_hub"
            st.rerun()
    with col2:
        if st.button("🔄 Re-attempt Assessment", use_container_width=True):
            st.session_state.edu_test_state = "taking_test"
            st.rerun()
    with col3:
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.edu_test_state = "dashboard"
            st.rerun()
