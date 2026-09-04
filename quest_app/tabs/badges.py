# -*- coding: utf-8 -*-
"""
QUEST Badges & Achievements Tab
===============================
Interactive, premium fintech/edtech achievements and learning streak tracker.
- Black / purple dark theme with violet accents and subtle glowing highlights.
- 10 Dynamic Badges calculated from actual user educational and portfolio data.
- 7-Day Learning Streak visualizer (M T W T F S S).
- Real-time Category Filtering and multi-criteria Sorting.
- Interactive Badge Details modal/card with working dismiss.
- Dynamic Statistics (Total XP, Badges Unlocked, Levels Completed, Active Streak).
- Chronological Recently Unlocked achievements feed with empty-state support.
- Safe, idempotent XP reward processing (never awards twice on reruns).
"""

from __future__ import annotations
import datetime as _dt
import html
import os
import streamlit as st

import edu_db
import ui_theme
from portfolio_ledger import get_transactions, load_holdings, HOLDINGS_FILE


# ══════════════════════════════════════════════════════════════════════════════
# HTML RENDERING UTILITY (Prevents Markdown Code Block Indentation Bugs)
# ══════════════════════════════════════════════════════════════════════════════

def _clean_html(html_str: str) -> str:
    """
    Strips leading and trailing whitespace from every line of an HTML string.
    This prevents CommonMark / Streamlit Markdown parser from treating indented lines
    (4+ spaces) as <pre><code> blocks, ensuring 100% native HTML component rendering.
    """
    lines = [line.strip() for line in html_str.strip().splitlines() if line.strip()]
    return "\n".join(lines)


def _render_html(html_str: str) -> None:
    """
    Renders custom HTML in Streamlit safely and reliably.
    """
    st.markdown(_clean_html(html_str), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 1. BADGE DEFINITIONS & ARTWORK
# ══════════════════════════════════════════════════════════════════════════════

def _get_badge_svg(badge_id: str, unlocked: bool = True, size: int = 72) -> str:
    """
    Returns crisp vector SVG badge artwork with neon glows and futuristic fintech geometry.
    If locked, applies monochrome filters and reduced opacity.
    """
    filter_style = "filter: drop-shadow(0 0 12px rgba(139, 92, 246, 0.45));" if unlocked else "filter: grayscale(100%); opacity: 0.4;"

    # Color palettes per badge
    palettes = {
        "first_steps": ("#8b5cf6", "#3b82f6", "#06b6d4"),
        "learning_explorer": ("#6366f1", "#8b5cf6", "#ec4899"),
        "diversifier": ("#10b981", "#06b6d4", "#3b82f6"),
        "tax_detective": ("#10b981", "#84cc16", "#059669"),
        "goal_setter": ("#ec4899", "#f43f5e", "#fb923c"),
        "seven_day_learner": ("#f97316", "#ef4444", "#eab308"),
        "comeback_learner": ("#a855f7", "#6366f1", "#38bdf8"),
        "quest_master": ("#fbbf24", "#f59e0b", "#d97706"),
    }
    c1, c2, c3 = palettes.get(badge_id, ("#8b5cf6", "#6366f1", "#3b82f6"))

    # Distinct center icon glyphs
    glyphs = {
        "first_steps": '<path d="M45 22L55 12L58 15L48 25L45 22Z" fill="#fff"/><path d="M28 52L22 58L25 61L31 55L28 52Z" fill="#fff"/><path d="M50 30L34 46L30 42L46 26L50 30Z" fill="url(#g_{bid})"/><circle cx="50" cy="30" r="3" fill="#fff"/>',
        "learning_explorer": '<path d="M24 32C24 28 34 26 40 30C46 26 56 28 56 32V54C50 50 44 50 40 53C36 50 30 50 24 54V32Z" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/><path d="M40 30V53" stroke="#fff" stroke-width="3" stroke-linecap="round"/>',
        "diversifier": '<rect x="25" y="25" width="12" height="12" rx="3" fill="#fff"/><rect x="43" y="25" width="12" height="12" rx="3" fill="url(#g_{bid})"/><rect x="25" y="43" width="12" height="12" rx="3" fill="url(#g_{bid})"/><rect x="43" y="43" width="12" height="12" rx="3" fill="#fff"/>',
        "tax_detective": '<path d="M26 24H54V56H26V24Z" rx="4" fill="none" stroke="#fff" stroke-width="3"/><path d="M32 32H48M32 40H42M32 48H44" stroke="url(#g_{bid})" stroke-width="2.5" stroke-linecap="round"/><circle cx="46" cy="46" r="5" fill="#10b981"/>',
        "goal_setter": '<circle cx="40" cy="40" r="18" fill="none" stroke="#fff" stroke-width="2.5"/><circle cx="40" cy="40" r="11" fill="none" stroke="url(#g_{bid})" stroke-width="2.5"/><circle cx="40" cy="40" r="5" fill="#fff"/>',
        "seven_day_learner": '<path d="M40 20C40 20 48 28 48 38C48 45 43 54 40 56C37 54 32 45 32 38C32 32 36 26 40 20Z" fill="url(#g_{bid})" stroke="#fff" stroke-width="2.5"/><circle cx="40" cy="42" r="4" fill="#fff"/>',
        "comeback_learner": '<path d="M26 38A14 14 0 1 1 30 48" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/><path d="M22 34L26 38L32 34" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="40" cy="40" r="4" fill="url(#g_{bid})"/>',
        "quest_master": '<path d="M24 50L28 28L36 38L40 24L44 38L52 28L56 50H24Z" fill="url(#g_{bid})" stroke="#fff" stroke-width="2.5" stroke-linejoin="round"/><circle cx="40" cy="24" r="3" fill="#fff"/><circle cx="28" cy="28" r="2.5" fill="#fff"/><circle cx="52" cy="28" r="2.5" fill="#fff"/>',
    }
    glyph_code = glyphs.get(badge_id, glyphs["first_steps"]).replace("{bid}", badge_id)

    svg_str = f"""<svg width="{size}" height="{size}" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style="{filter_style}; transition: transform 0.2s ease;">
<defs>
<linearGradient id="g_{badge_id}" x1="0%" y1="0%" x2="100%" y2="100%">
<stop offset="0%" stop-color="{c1}" />
<stop offset="50%" stop-color="{c2}" />
<stop offset="100%" stop-color="{c3}" />
</linearGradient>
<linearGradient id="bg_{badge_id}" x1="0%" y1="0%" x2="100%" y2="100%">
<stop offset="0%" stop-color="{c1}" stop-opacity="0.25" />
<stop offset="100%" stop-color="{c3}" stop-opacity="0.08" />
</linearGradient>
</defs>
<polygon points="40,4 68,16 76,44 60,72 20,72 4,44 12,16" fill="url(#bg_{badge_id})" stroke="url(#g_{badge_id})" stroke-width="2.5" stroke-linejoin="round"/>
<circle cx="40" cy="40" r="24" fill="rgba(15, 17, 23, 0.75)" stroke="url(#g_{badge_id})" stroke-width="1.5" stroke-dasharray="3 3"/>
{glyph_code}
</svg>"""
    return _clean_html(svg_str)


def get_badge_definitions() -> list[dict]:
    """
    Returns the official 10 Badges with metadata, categories, rewards, and unlock rules.
    """
    return [
        {
            "id": "first_steps",
            "name": "First Steps",
            "description": "Complete your first learning level.",
            "category": "Learning",
            "reward_xp": 50,
            "target": 1,
            "requirement_text": "Complete at least 1 educational level in the Learning Path.",
            "rule_type": "levels_count",
        },
        {
            "id": "learning_explorer",
            "name": "Learning Explorer",
            "description": "Complete 5 educational lessons.",
            "category": "Learning",
            "reward_xp": 50,
            "target": 5,
            "requirement_text": "Watch and complete 5 video lessons in the Knowledge Library.",
            "rule_type": "articles_count",
        },
        {
            "id": "diversifier",
            "name": "Diversifier",
            "description": "Complete the Portfolio Builder challenge.",
            "category": "Portfolio",
            "reward_xp": 50,
            "target": 1,
            "requirement_text": "Complete Module 5 (Build Your Portfolio) or hold 3+ diverse assets in your portfolio.",
            "rule_type": "module_or_portfolio",
            "target_module": "module_5",
        },
        {
            "id": "tax_detective",
            "name": "Tax Detective",
            "description": "Complete the Tax Detective challenge.",
            "category": "Tax",
            "reward_xp": 30,
            "target": 1,
            "requirement_text": "Complete Module 10 (Tax Detective) or solve the Tax Detective challenge.",
            "rule_type": "specific_module",
            "target_module": "module_10",
        },
        {
            "id": "goal_setter",
            "name": "Goal Setter",
            "description": "Complete the Reach Your Goal level.",
            "category": "Consistency",
            "reward_xp": 50,
            "target": 1,
            "requirement_text": "Complete Module 3 (Reach Your Goal) in the Learning Path.",
            "rule_type": "specific_module",
            "target_module": "module_3",
        },
        {
            "id": "seven_day_learner",
            "name": "7-Day Learner",
            "description": "Maintain a 7-day learning streak.",
            "category": "Consistency",
            "reward_xp": 50,
            "target": 7,
            "requirement_text": "Maintain an active learning streak for 7 consecutive days.",
            "rule_type": "streak_count",
        },
        {
            "id": "comeback_learner",
            "name": "Comeback Learner",
            "description": "Successfully complete a replayed challenge.",
            "category": "Consistency",
            "reward_xp": 50,
            "target": 1,
            "requirement_text": "Revisit and replay any completed level, quiz, or challenge.",
            "rule_type": "replay_challenge",
        },
        {
            "id": "quest_master",
            "name": "QUEST Master",
            "description": "Complete all 9 game levels + Tax Detective.",
            "category": "Consistency",
            "reward_xp": 100,
            "target": 10,
            "requirement_text": "Master and complete all 10 educational modules in the QUEST curriculum.",
            "rule_type": "quest_master_all",
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 2. PROGRESS & STREAK CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _extract_activity_dates(prog: dict, tx_list: list) -> set[str]:
    """
    Extracts all unique YYYY-MM-DD dates where the user performed learning or portfolio actions.
    """
    dates = set()
    
    # 1. Recorded activity dates in progress
    for d_str in prog.get("activity_dates", []):
        if isinstance(d_str, str) and len(d_str) >= 10:
            dates.add(d_str[:10])

    # 2. Badge unlock dates
    for b in prog.get("badges", []):
        if isinstance(b, dict) and b.get("unlocked_at"):
            dates.add(b["unlocked_at"][:10])

    # 3. Transaction timestamps
    for tx in tx_list:
        ts = tx.get("timestamp", "")
        if ts and len(ts) >= 10:
            dates.add(ts[:10])

    # 4. Learning log timestamps from adaptive_engine
    try:
        from adaptive_engine import get_learning_log
        for l in get_learning_log():
            dt_s = l.get("date", "")
            if dt_s and len(dt_s) >= 10:
                dates.add(dt_s[:10])
    except Exception:
        pass

    # Today is always active if user is logged into the platform
    today_str = _dt.date.today().isoformat()
    dates.add(today_str)

    return dates


def calculate_streak(active_dates: set[str]) -> tuple[int, list[dict]]:
    """
    Calculates current consecutive day streak and returns a 7-day visualization structure.
    """
    today = _dt.date.today()
    
    # Check streak ending at today or yesterday
    current_streak = 0
    check_day = today
    
    # If today is in active_dates, start from today
    if check_day.isoformat() in active_dates:
        while check_day.isoformat() in active_dates:
            current_streak += 1
            check_day -= _dt.timedelta(days=1)
    else:
        # Check if yesterday was active
        check_day = today - _dt.timedelta(days=1)
        while check_day.isoformat() in active_dates:
            current_streak += 1
            check_day -= _dt.timedelta(days=1)

    # Build 7-day display (Monday to Sunday of the current week)
    start_of_week = today - _dt.timedelta(days=today.weekday())  # Monday
    week_days = []
    day_letters = ["M", "T", "W", "T", "F", "S", "S"]
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for i in range(7):
        d = start_of_week + _dt.timedelta(days=i)
        iso = d.isoformat()
        is_active = iso in active_dates
        is_today = (d == today)
        is_past_or_today = (d <= today)
        
        week_days.append({
            "letter": day_letters[i],
            "name": day_names[i],
            "date_num": d.strftime("%d"),
            "date_str": d.strftime("%b %d"),
            "is_active": is_active,
            "is_today": is_today,
            "is_past": is_past_or_today,
        })

    return current_streak, week_days


def _ensure_edu_dir(user_info: dict | None = None):
    """Ensures edu_db has an active user directory set before calling progress functions."""
    if edu_db._data_dir is None:
        uname = None
        if user_info and user_info.get("username"):
            uname = user_info["username"]
        elif hasattr(st, "session_state") and st.session_state.get("_quest_username"):
            uname = st.session_state.get("_quest_username")
        elif hasattr(st, "session_state") and st.session_state.get("user_info"):
            uname = st.session_state.user_info.get("username")
        if not uname:
            uname = "default_user"
        _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        user_dir = os.path.join(_here, "users", uname)
        os.makedirs(user_dir, exist_ok=True)
        edu_db.set_data_dir(user_dir, username=uname)


def get_user_progress_data(user_info: dict | None = None) -> dict:
    """
    Fetches raw progress data safely from edu_db, portfolio_ledger, and session state.
    """
    _ensure_edu_dir(user_info)
    prog = edu_db.load_progress()
    try:
        tx_list = get_transactions()
    except Exception:
        tx_list = []

    try:
        holdings = load_holdings(HOLDINGS_FILE) if os.path.exists(HOLDINGS_FILE) else []
    except Exception:
        holdings = []

    active_dates = _extract_activity_dates(prog, tx_list)
    streak_count, week_days = calculate_streak(active_dates)

    # Save today's activity date into prog if not present
    today_str = _dt.date.today().isoformat()
    raw_dates = prog.get("activity_dates", [])
    if today_str not in raw_dates:
        raw_dates.append(today_str)
        prog["activity_dates"] = raw_dates
        edu_db.save_progress(prog)

    return {
        "prog": prog,
        "tx_list": tx_list,
        "holdings": holdings,
        "active_dates": active_dates,
        "streak_count": streak_count,
        "week_days": week_days,
        "total_xp": prog.get("total_xp", 0),
        "completed_articles": prog.get("completed_articles", []),
        "completed_levels": prog.get("completed_levels", []),
        "saved_badges": prog.get("badges", []),
    }


def evaluate_badge(badge_def: dict, user_data: dict) -> dict:
    """
    Evaluates current progress, target, unlock status, and unlock date for a single badge.
    """
    bid = badge_def["id"]
    rule = badge_def["rule_type"]
    target = badge_def["target"]
    prog = user_data["prog"]
    saved_badges = user_data["saved_badges"]

    completed_articles = user_data["completed_articles"]
    completed_levels = user_data["completed_levels"]
    holdings = user_data["holdings"]
    streak_count = user_data["streak_count"]

    # Check if badge was previously recorded as unlocked in saved_badges
    saved_badge_record = None
    for b in saved_badges:
        if isinstance(b, dict) and b.get("id") == bid:
            saved_badge_record = b
            break
        elif isinstance(b, str) and b == bid:
            saved_badge_record = {"id": bid, "unlocked_at": "2026-08-24T12:00:00"}
            break

    # Calculate actual metric progress
    current_progress = 0
    is_unlocked = False

    if rule == "levels_count":
        current_progress = len(completed_levels)
        is_unlocked = current_progress >= target

    elif rule == "articles_count":
        current_progress = len(completed_articles)
        is_unlocked = current_progress >= target

    elif rule == "module_or_portfolio":
        target_mod = badge_def.get("target_module", "module_5")
        has_mod = target_mod in completed_levels or "level_5" in completed_levels or "portfolio_builder" in completed_levels
        has_holdings = len(holdings) >= 3
        current_progress = 1 if (has_mod or has_holdings) else (1 if len(holdings) > 0 else 0)
        is_unlocked = has_mod or has_holdings

    elif rule == "specific_module":
        target_mod = badge_def.get("target_module", "")
        clean_name = target_mod.replace("module_", "").lower()
        has_mod = (target_mod in completed_levels 
                    or f"level_{clean_name}" in completed_levels 
                    or f"{clean_name}" in completed_levels
                    or any(clean_name in str(lvl).lower() for lvl in completed_levels))
        current_progress = 1 if has_mod else 0
        is_unlocked = has_mod

    elif rule == "streak_count":
        current_progress = streak_count
        is_unlocked = current_progress >= target

    elif rule == "replay_challenge":
        replays = prog.get("replayed_challenges_count", 0)
        current_progress = 1 if replays >= 1 else 0
        is_unlocked = replays >= 1

    elif rule == "quest_master_all":
        # 10 distinct modules in catalog
        current_progress = len(completed_levels)
        is_unlocked = current_progress >= target

    # If already recorded in database as unlocked, keep it unlocked
    if saved_badge_record:
        is_unlocked = True
        current_progress = max(current_progress, target)

    # Determine unlock date string
    unlock_date_str = None
    raw_unlock_iso = None
    if is_unlocked:
        if saved_badge_record and saved_badge_record.get("unlocked_at"):
            raw_unlock_iso = saved_badge_record["unlocked_at"]
            try:
                parsed_d = _dt.datetime.fromisoformat(raw_unlock_iso.replace("Z", ""))
                unlock_date_str = parsed_d.strftime("%b %d, %Y")
            except Exception:
                unlock_date_str = raw_unlock_iso[:10]
        else:
            raw_unlock_iso = _dt.datetime.now().isoformat()
            unlock_date_str = _dt.date.today().strftime("%b %d, %Y")

    progress_capped = min(current_progress, target)
    progress_pct = int((progress_capped / target) * 100) if target > 0 else 100

    return {
        **badge_def,
        "unlocked": is_unlocked,
        "progress": progress_capped,
        "progress_pct": progress_pct,
        "unlock_date_str": unlock_date_str,
        "unlock_date_iso": raw_unlock_iso,
        "is_persisted": saved_badge_record is not None,
    }


def sync_and_award_badge_xp(evaluated_badges: list[dict], user_data: dict) -> bool:
    """
    Idempotently syncs newly unlocked badges to edu_progress.json and awards their XP.
    XP is awarded ONCE and never repeatedly on subsequent reruns.
    """
    prog = user_data["prog"]
    saved_badges = prog.get("badges", [])
    
    # Build map of already awarded badge IDs
    awarded_ids = set()
    formatted_saved_badges = []

    for b in saved_badges:
        if isinstance(b, dict):
            awarded_ids.add(b.get("id"))
            formatted_saved_badges.append(b)
        elif isinstance(b, str):
            awarded_ids.add(b)
            formatted_saved_badges.append({
                "id": b,
                "unlocked_at": _dt.datetime.now().isoformat(),
                "xp_awarded": 50,
            })

    state_changed = False
    xp_to_add = 0

    for eb in evaluated_badges:
        bid = eb["id"]
        if eb["unlocked"] and bid not in awarded_ids:
            # Newly unlocked achievement!
            awarded_ids.add(bid)
            now_iso = _dt.datetime.now().isoformat()
            formatted_saved_badges.append({
                "id": bid,
                "unlocked_at": now_iso,
                "xp_awarded": eb["reward_xp"],
            })
            xp_to_add += eb["reward_xp"]
            state_changed = True
            eb["unlock_date_iso"] = now_iso
            eb["unlock_date_str"] = _dt.date.today().strftime("%b %d, %Y")

    if state_changed:
        prog["badges"] = formatted_saved_badges
        prog["total_xp"] = prog.get("total_xp", 0) + xp_to_add
        edu_db.save_progress(prog)
        return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
# 3. CSS STYLING & THEMING (Black/Purple Dark Aesthetic)
# ══════════════════════════════════════════════════════════════════════════════

def _inject_badges_css():
    """
    Injects custom responsive CSS adhering strictly to the black/purple fintech look.
    """
    css_content = """
<style>
/* ── Badges Page Container ── */
.quest-badges-wrap {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    animation: q-page-in 0.35s cubic-bezier(.22,.61,.36,1);
}

/* ── Header ── */
.qb-header {
    margin-bottom: 0.5rem;
}
.qb-header h1 {
    font-size: 2.1rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, #ffffff 0%, #e2e8f0 50%, #c084fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 4px 0;
}
.qb-header p {
    color: #94a3b8;
    font-size: 0.95rem;
    margin: 0;
}

/* ── Stat Cards Grid ── */
.qb-stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 1rem;
}
.qb-stat-card {
    background: linear-gradient(180deg, rgba(30, 27, 50, 0.75) 0%, rgba(18, 16, 32, 0.9) 100%);
    border: 1px solid rgba(168, 85, 247, 0.22);
    border-radius: 14px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.45);
    transition: transform 0.18s ease, border-color 0.18s ease;
}
.qb-stat-card:hover {
    transform: translateY(-2px);
    border-color: rgba(168, 85, 247, 0.45);
    box-shadow: 0 12px 28px -4px rgba(168, 85, 247, 0.15);
}
.qb-stat-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #a78bfa;
    display: flex;
    align-items: center;
    gap: 6px;
}
.qb-stat-val {
    font-size: 1.65rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #f8fafc;
    margin-top: 6px;
}
.qb-stat-sub {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 2px;
}

/* ── Learning Streak Card ── */
.qb-streak-card {
    background: linear-gradient(135deg, rgba(30, 20, 50, 0.8) 0%, rgba(15, 12, 28, 0.95) 100%);
    border: 1px solid rgba(192, 132, 252, 0.3);
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 0 10px 30px -8px rgba(0, 0, 0, 0.6);
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.qb-streak-card::before {
    content: '';
    position: absolute;
    top: -60px;
    right: -60px;
    width: 160px;
    height: 160px;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.25) 0%, rgba(0, 0, 0, 0) 70%);
    pointer-events: none;
}
.qb-streak-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 10px;
}
.qb-streak-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #f8fafc;
    display: flex;
    align-items: center;
    gap: 8px;
}
.qb-streak-count-pill {
    background: rgba(168, 85, 247, 0.18);
    border: 1px solid rgba(168, 85, 247, 0.4);
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #e9d5ff;
    font-family: 'JetBrains Mono', monospace;
}
.qb-days-row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 16px;
}
.qb-day-bubble {
    flex: 1;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 10px 4px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    transition: all 0.2s ease;
}
.qb-day-bubble.active {
    background: linear-gradient(180deg, rgba(168, 85, 247, 0.25) 0%, rgba(139, 92, 246, 0.1) 100%);
    border-color: rgba(168, 85, 247, 0.6);
    box-shadow: 0 0 14px rgba(168, 85, 247, 0.2);
}
.qb-day-bubble.today {
    border-color: #c084fc;
    outline: 2px solid rgba(192, 132, 252, 0.4);
}
.qb-day-letter {
    font-size: 0.75rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
}
.qb-day-bubble.active .qb-day-letter {
    color: #e9d5ff;
}
.qb-day-icon {
    font-size: 0.95rem;
}
.qb-day-date {
    font-size: 0.7rem;
    color: #64748b;
    font-family: 'JetBrains Mono', monospace;
}
.qb-day-bubble.active .qb-day-date {
    color: #c084fc;
}
.qb-streak-bar-bg {
    width: 100%;
    height: 7px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    overflow: hidden;
    margin-top: 6px;
}
.qb-streak-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #8b5cf6 0%, #a855f7 50%, #ec4899 100%);
    border-radius: 999px;
    transition: width 0.6s ease;
}

/* ── Badge Grid ── */
.qb-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
    gap: 16px;
    margin-bottom: 2rem;
}
.qb-card {
    background: linear-gradient(180deg, rgba(24, 22, 38, 0.9) 0%, rgba(15, 14, 25, 0.95) 100%);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 16px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
    transition: all 0.22s cubic-bezier(.22,.61,.36,1);
}
.qb-card.unlocked {
    border-color: rgba(168, 85, 247, 0.35);
    box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.5), 0 0 16px -4px rgba(168, 85, 247, 0.12);
    animation: qb-badge-float 3.4s ease-in-out infinite;
    will-change: transform;
}
.qb-card.unlocked:hover {
    animation-play-state: paused;
    transform: translateY(-5px) scale(1.035);
    border-color: rgba(168, 85, 247, 0.65);
    box-shadow: 0 14px 32px -4px rgba(0, 0, 0, 0.65), 0 0 24px rgba(168, 85, 247, 0.25);
    transition: transform 0.28s cubic-bezier(.22,.61,.36,1), border-color 0.22s ease, box-shadow 0.22s ease;
}
@keyframes qb-badge-float {
    0%, 100% {
        transform: translateY(0px);
    }
    50% {
        transform: translateY(-6px);
    }
}
@media (prefers-reduced-motion: reduce) {
    .qb-card.unlocked {
        animation: none;
    }
}
.qb-card.locked {
    border-color: rgba(255, 255, 255, 0.05);
    background: rgba(18, 17, 26, 0.6);
    opacity: 0.88;
    animation: none;
}
.qb-card.locked:hover {
    border-color: rgba(255, 255, 255, 0.12);
    opacity: 1;
}
.qb-card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 14px;
}
.qb-card-icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
}
.qb-card-icon-wrap.just-unlocked {
    border-radius: 50%;
    animation: qb-icon-unlock-spin 0.7s cubic-bezier(.34,1.56,.64,1) 1 both,
               qb-icon-unlock-pulse 0.7s ease-out 1;
}
@keyframes qb-icon-unlock-spin {
    0% {
        transform: rotate(0deg) scale(0.82);
    }
    55% {
        transform: rotate(360deg) scale(1.15);
    }
    100% {
        transform: rotate(360deg) scale(1);
    }
}
@keyframes qb-icon-unlock-pulse {
    0% {
        box-shadow: 0 0 0 0 rgba(192, 132, 252, 0);
    }
    35% {
        box-shadow: 0 0 22px 6px rgba(192, 132, 252, 0.55);
    }
    100% {
        box-shadow: 0 0 0 0 rgba(192, 132, 252, 0);
    }
}
@media (prefers-reduced-motion: reduce) {
    .qb-card-icon-wrap.just-unlocked {
        animation: none;
    }
}
.qb-status-tag {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.qb-status-tag.unlocked {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.35);
}
.qb-status-tag.locked {
    background: rgba(255, 255, 255, 0.06);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.qb-card-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0 0 4px 0;
}
.qb-card-cat {
    font-size: 0.72rem;
    font-weight: 600;
    color: #a78bfa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.qb-card-desc {
    font-size: 0.83rem;
    color: #94a3b8;
    line-height: 1.4;
    margin-bottom: 14px;
    min-height: 2.4rem;
}
.qb-card-footer {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.qb-progress-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #94a3b8;
    font-family: 'JetBrains Mono', monospace;
}
.qb-progress-bar {
    width: 100%;
    height: 5px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    overflow: hidden;
}
.qb-progress-fill {
    height: 100%;
    background: #34d399;
    border-radius: 999px;
}
.qb-progress-fill.locked {
    background: #8b5cf6;
}
.qb-card-reward {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.78rem;
    color: #facc15;
    font-weight: 600;
}
.qb-unlock-date {
    font-size: 0.72rem;
    color: #64748b;
    font-style: italic;
}

/* ── Details Card / Modal ── */
.qb-detail-modal {
    background: linear-gradient(135deg, rgba(28, 22, 45, 0.98) 0%, rgba(16, 14, 26, 0.98) 100%);
    border: 1px solid rgba(168, 85, 247, 0.4);
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.7), 0 0 30px rgba(168, 85, 247, 0.2);
    margin-bottom: 2rem;
    animation: q-fade 0.25s ease-out;
}
.qb-detail-content {
    display: flex;
    gap: 24px;
    align-items: center;
    flex-wrap: wrap;
}
.qb-detail-info {
    flex: 1;
    min-width: 260px;
}
.qb-detail-title {
    font-size: 1.6rem;
    font-weight: 800;
    color: #f8fafc;
    margin: 0 0 6px 0;
}

/* ── Recently Unlocked Feed ── */
.qb-recent-section {
    background: linear-gradient(180deg, rgba(22, 19, 36, 0.7) 0%, rgba(14, 13, 22, 0.85) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 2rem;
}
.qb-recent-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.qb-recent-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
}
.qb-recent-item {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(168, 85, 247, 0.2);
    border-radius: 12px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: transform 0.15s ease;
}
.qb-recent-item:hover {
    transform: translateY(-2px);
    background: rgba(168, 85, 247, 0.08);
}
.qb-recent-name {
    font-size: 0.9rem;
    font-weight: 600;
    color: #f8fafc;
}
.qb-recent-date {
    font-size: 0.72rem;
    color: #94a3b8;
}
.qb-recent-xp {
    margin-left: auto;
    font-size: 0.8rem;
    font-weight: 700;
    color: #34d399;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Empty State ── */
.qb-empty-state {
    text-align: center;
    padding: 32px 20px;
    color: #94a3b8;
}
.qb-empty-icon {
    font-size: 2.5rem;
    margin-bottom: 8px;
}

/* Responsive */
@media (max-width: 768px) {
    .qb-stats-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .qb-grid {
        grid-template-columns: 1fr;
    }
    .qb-days-row {
        overflow-x: auto;
    }
}
</style>
"""
    _render_html(css_content)


# ══════════════════════════════════════════════════════════════════════════════
# 4. RENDER FUNCTIONS FOR EACH SECTION
# ══════════════════════════════════════════════════════════════════════════════

def render_header():
    """Renders page title and subtitle."""
    header_html = """
<div class="qb-header">
    <h1>Badges & Achievements</h1>
    <p>Keep learning. Keep progressing. Collect your achievements.</p>
</div>
"""
    _render_html(header_html)


def render_statistics(total_xp: int, unlocked_count: int, total_badges: int, 
                      completed_levels_count: int, total_levels: int, streak_count: int):
    """
    Renders the 4 dynamic fintech stat cards using actual user progress.
    """
    unlocked_pct = int((unlocked_count / total_badges) * 100) if total_badges > 0 else 0
    html_block = f"""
<div class="qb-stats-grid">
    <div class="qb-stat-card">
        <div class="qb-stat-label">⭐ Total XP</div>
        <div class="qb-stat-val" style="color: #facc15;">{total_xp:,}</div>
        <div class="qb-stat-sub">Lifetime Earned</div>
    </div>
    <div class="qb-stat-card">
        <div class="qb-stat-label">🏆 Badges</div>
        <div class="qb-stat-val" style="color: #38bdf8;">{unlocked_count} <span style="font-size: 1rem; color: #64748b;">/ {total_badges}</span></div>
        <div class="qb-stat-sub">{unlocked_pct}% Unlocked</div>
    </div>
    <div class="qb-stat-card">
        <div class="qb-stat-label">🎓 Levels</div>
        <div class="qb-stat-val" style="color: #a78bfa;">{completed_levels_count} <span style="font-size: 1rem; color: #64748b;">/ {total_levels}</span></div>
        <div class="qb-stat-sub">Curriculum Progress</div>
    </div>
    <div class="qb-stat-card">
        <div class="qb-stat-label">🔥 Learning Streak</div>
        <div class="qb-stat-val" style="color: #fb923c;">{streak_count} <span style="font-size: 1rem; color: #64748b;">Days</span></div>
        <div class="qb-stat-sub">Active Routine</div>
    </div>
</div>
"""
    _render_html(html_block)


def render_streak(streak_count: int, week_days: list[dict]):
    """
    Renders 7-day learning streak tracker visualization (M T W T F S S).
    """
    day_bubbles_html = ""
    for d in week_days:
        active_cls = "active" if d["is_active"] else ""
        today_cls = "today" if d["is_today"] else ""
        icon = "🔥" if d["is_active"] else ("⏳" if d["is_today"] else "○")
        
        day_bubbles_html += f"""<div class="qb-day-bubble {active_cls} {today_cls}" title="{d['name']}: {'Active' if d['is_active'] else 'Inactive'}">
<span class="qb-day-letter">{d['letter']}</span>
<span class="qb-day-icon">{icon}</span>
<span class="qb-day-date">{d['date_num']}</span>
</div>"""

    streak_pct = min(100, int((streak_count / 7) * 100))

    html_streak = f"""
<div class="qb-streak-card">
    <div class="qb-streak-top">
        <div class="qb-streak-title">
            <span>🔥 7-Day Learning Streak</span>
        </div>
        <div class="qb-streak-count-pill">
            {streak_count} / 7 Days Active ({streak_pct}%)
        </div>
    </div>
    <div class="qb-days-row">
        {day_bubbles_html}
    </div>
    <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94a3b8;">
        <span>Current Routine Progress</span>
        <span style="font-weight:600; color:#c084fc;">{streak_count} Days Consecutive</span>
    </div>
    <div class="qb-streak-bar-bg">
        <div class="qb-streak-bar-fill" style="width: {streak_pct}%;"></div>
    </div>
</div>
"""
    _render_html(html_streak)


def render_interactive_details(selected_badge: dict):
    """
    Renders detailed interactive badge inspector when a user selects a badge.
    """
    bid = selected_badge["id"]
    unlocked = selected_badge["unlocked"]
    svg_artwork = _get_badge_svg(bid, unlocked=unlocked, size=100)

    status_badge_html = ('<span class="qb-status-tag unlocked">✓ Achievement Unlocked!</span>' 
                         if unlocked 
                         else '<span class="qb-status-tag locked">🔒 Badge Locked</span>')

    unlock_info_html = (f'<div style="color: #34d399; font-size: 0.85rem; margin-top: 8px;">🎉 Unlocked on <strong>{selected_badge["unlock_date_str"]}</strong> • Earned +{selected_badge["reward_xp"]} XP</div>'
                        if unlocked
                        else f'<div style="color: #94a3b8; font-size: 0.85rem; margin-top: 8px;">🎯 Target: <strong>{selected_badge["progress"]} / {selected_badge["target"]}</strong> ({selected_badge["progress_pct"]}%) • Reward: +{selected_badge["reward_xp"]} XP</div>')

    details_html = f"""
<div class="qb-detail-modal">
    <div class="qb-detail-content">
        <div style="flex: 0 0 100px; text-align:center;">
            {svg_artwork}
        </div>
        <div class="qb-detail-info">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
                {status_badge_html}
                <span style="color:#a78bfa; font-size:0.75rem; text-transform:uppercase; font-weight:600;">{selected_badge['category']}</span>
            </div>
            <div class="qb-detail-title">{selected_badge['name']}</div>
            <div style="color:#e2e8f0; font-size:0.95rem; margin-bottom:8px;">{selected_badge['description']}</div>
            <div style="color:#94a3b8; font-size:0.85rem; background:rgba(255,255,255,0.04); padding:10px 14px; border-radius:10px; border:1px solid rgba(255,255,255,0.06);">
                <strong>Requirement:</strong> {selected_badge['requirement_text']}
            </div>
            {unlock_info_html}
        </div>
    </div>
</div>
"""
    _render_html(details_html)

    c_close, _ = st.columns([1, 4])
    with c_close:
        if st.button("✕ Close Inspector", key=f"btn_close_badge_{bid}", use_container_width=True):
            st.session_state.badges_selected_id = None
            st.rerun()


def render_recently_unlocked(unlocked_badges: list[dict]):
    """
    Renders chronological recently unlocked achievements section as a single cohesive DOM element.
    """
    if not unlocked_badges:
        inner_content = """
<div class="qb-empty-state">
    <div class="qb-empty-icon">🎖️</div>
    <div style="font-weight:600; color:#e2e8f0; margin-bottom:4px;">No Badges Unlocked Yet</div>
    <div style="font-size:0.85rem;">Start completing educational lessons in the Library or Learning Path to earn achievements!</div>
</div>
"""
    else:
        # Sort by unlock_date_iso descending
        sorted_recent = sorted(
            unlocked_badges, 
            key=lambda x: str(x.get("unlock_date_iso") or ""), 
            reverse=True
        )[:6]

        items_html = ""
        for b in sorted_recent:
            mini_svg = _get_badge_svg(b["id"], unlocked=True, size=40)
            items_html += f"""
<div class="qb-recent-item">
    <div style="flex:0 0 40px;">{mini_svg}</div>
    <div>
        <div class="qb-recent-name">{b['name']}</div>
        <div class="qb-recent-date">{b['unlock_date_str']}</div>
    </div>
    <div class="qb-recent-xp">+{b['reward_xp']} XP</div>
</div>
"""
        inner_content = f'<div class="qb-recent-list">{items_html}</div>'

    full_recent_html = f"""
<div class="qb-recent-section">
    <div class="qb-recent-title">⚡ Recently Unlocked</div>
    {inner_content}
</div>
"""
    _render_html(full_recent_html)


def render_badge_grid(badges: list[dict], newly_unlocked_ids: set[str] | None = None):
    """
    Renders the responsive badge grid with interactive selection buttons.
    """
    if not badges:
        st.info("No achievements match the selected category filter.")
        return

    newly_unlocked_ids = newly_unlocked_ids or set()

    # Render in Streamlit columns for full interactivity
    cols_per_row = 3
    for i in range(0, len(badges), cols_per_row):
        row_badges = badges[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for idx, b in enumerate(row_badges):
            with cols[idx]:
                unlocked = b["unlocked"]
                card_cls = "unlocked" if unlocked else "locked"
                svg_icon = _get_badge_svg(b["id"], unlocked=unlocked, size=64)
                icon_wrap_cls = "qb-card-icon-wrap just-unlocked" if b["id"] in newly_unlocked_ids else "qb-card-icon-wrap"
                
                status_tag = ('<span class="qb-status-tag unlocked">✓ Unlocked</span>' 
                              if unlocked 
                              else '<span class="qb-status-tag locked">🔒 Locked</span>')

                progress_fill_cls = "locked" if not unlocked else ""
                
                card_html = f"""
<div class="qb-card {card_cls}">
    <div class="qb-card-top">
        <div class="{icon_wrap_cls}">{svg_icon}</div>
        {status_tag}
    </div>
    <div>
        <div class="qb-card-cat">{b['category']}</div>
        <div class="qb-card-title">{b['name']}</div>
        <div class="qb-card-desc">{b['description']}</div>
    </div>
    <div class="qb-card-footer">
        <div class="qb-progress-meta">
            <span>Progress</span>
            <span>{b['progress']} / {b['target']}</span>
        </div>
        <div class="qb-progress-bar">
            <div class="qb-progress-fill {progress_fill_cls}" style="width: {b['progress_pct']}%;"></div>
        </div>
        <div class="qb-card-reward">
            <span>⭐ +{b['reward_xp']} XP</span>
            <span class="qb-unlock-date">{b['unlock_date_str'] if unlocked else 'Locked'}</span>
        </div>
    </div>
</div>
"""
                _render_html(card_html)
                
                btn_label = f"Inspect {b['name']}"
                if st.button(btn_label, key=f"btn_inspect_{b['id']}", use_container_width=True):
                    st.session_state.badges_selected_id = b["id"]
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAIN TAB ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def render(user_info: dict | None = None):
    """
    Main render function for the Badges & Achievements tab.
    """
    # 1. Inject styling
    _inject_badges_css()

    # 2. Fetch live user progress
    user_data = get_user_progress_data(user_info)
    badge_defs = get_badge_definitions()

    # 3. Evaluate each badge dynamically
    evaluated_badges = [evaluate_badge(b, user_data) for b in badge_defs]

    # 4. Idempotently award any newly unlocked badge XP (never double-awarded)
    if sync_and_award_badge_xp(evaluated_badges, user_data):
        # Refresh progress data after syncing
        user_data = get_user_progress_data(user_info)

    # 4b. Badges unlocked for the first time on this run get a one-time icon
    #     animation. Uses the existing is_persisted flag from evaluate_badge
    #     (set before syncing) — no change to badge detection/storage/XP logic.
    #     Once persisted, is_persisted is True on the next rerun, so the
    #     animation naturally never replays.
    newly_unlocked_ids = {b["id"] for b in evaluated_badges if b["unlocked"] and not b["is_persisted"]}

    # 5. Calculate summary metrics
    unlocked_list = [b for b in evaluated_badges if b["unlocked"]]
    unlocked_count = len(unlocked_list)
    total_badges = len(evaluated_badges)
    total_xp = user_data["total_xp"]
    completed_levels_count = len(user_data["completed_levels"])
    total_levels = 10  # 10 catalog modules in QUEST
    streak_count = user_data["streak_count"]

    # 6. Render Header
    render_header()

    # 7. Render Statistics Cards
    render_statistics(
        total_xp=total_xp,
        unlocked_count=unlocked_count,
        total_badges=total_badges,
        completed_levels_count=completed_levels_count,
        total_levels=total_levels,
        streak_count=streak_count,
    )

    # 8. Render 7-Day Learning Streak Section
    render_streak(streak_count, user_data["week_days"])

    # 9. Interactive Badge Details (if selected)
    if "badges_selected_id" not in st.session_state:
        st.session_state.badges_selected_id = None

    selected_id = st.session_state.badges_selected_id
    if selected_id:
        selected_badge_obj = next((b for b in evaluated_badges if b["id"] == selected_id), None)
        if selected_badge_obj:
            render_interactive_details(selected_badge_obj)

    # 10. Controls: Category Filters & Sorting
    c_filter, c_sort = st.columns([3, 2])
    
    categories = ["All", "Learning", "Portfolio", "Market", "Tax", "Consistency"]
    with c_filter:
        selected_category = st.radio(
            "Filter Category",
            categories,
            horizontal=True,
            key="badges_category_radio",
            label_visibility="collapsed"
        )

    sort_options = ["Recent", "Oldest", "Unlocked First", "Locked First", "XP Reward"]
    with c_sort:
        selected_sort = st.selectbox(
            "Sort Achievements",
            sort_options,
            key="badges_sort_select",
            label_visibility="collapsed"
        )

    # Filter badges
    filtered_badges = evaluated_badges
    if selected_category != "All":
        filtered_badges = [b for b in filtered_badges if b["category"] == selected_category]

    # Sort badges
    if selected_sort == "Recent":
        # Unlocked with recent dates first, then locked
        filtered_badges = sorted(
            filtered_badges, 
            key=lambda x: (1 if x["unlocked"] else 0, str(x.get("unlock_date_iso") or "")), 
            reverse=True
        )
    elif selected_sort == "Oldest":
        filtered_badges = sorted(
            filtered_badges, 
            key=lambda x: (1 if x["unlocked"] else 0, str(x.get("unlock_date_iso") or "9999")), 
            reverse=False
        )
    elif selected_sort == "Unlocked First":
        filtered_badges = sorted(filtered_badges, key=lambda x: 1 if x["unlocked"] else 0, reverse=True)
    elif selected_sort == "Locked First":
        filtered_badges = sorted(filtered_badges, key=lambda x: 1 if x["unlocked"] else 0, reverse=False)
    elif selected_sort == "XP Reward":
        filtered_badges = sorted(filtered_badges, key=lambda x: x["reward_xp"], reverse=True)

    # 11. Render Badge Grid
    render_badge_grid(filtered_badges, newly_unlocked_ids=newly_unlocked_ids)

    # 12. Render Recently Unlocked Section
    render_recently_unlocked(unlocked_list)