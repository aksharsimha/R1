import sys
import os
import re
import html
import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go
import time
import json as _mcj
import uuid as _uuid
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings, get_predictions
import nse_live as _nse


def _render_html_table(rows):
    if not rows:
        return ""
    html_out = ['<table style="width:100%;border-collapse:collapse;margin:8px 0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:8px;overflow:hidden;">']
    is_header = True
    for r in rows:
        cells = [c.strip() for c in r.strip('|').split('|')]
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            is_header = False
            continue
        html_out.append('<tr>')
        for c in cells:
            tag = 'th' if is_header else 'td'
            style = 'padding:6px 10px;border:1px solid rgba(255,255,255,0.08);font-size:0.82rem;'
            if is_header:
                style += 'background:rgba(139,92,246,0.18);color:#c084fc;font-weight:700;text-align:left;'
            else:
                style += 'color:#e2e8f0;line-height:1.4;'
            c_fmt = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c)
            html_out.append(f'<{tag} style="{style}">{c_fmt}</{tag}>')
        html_out.append('</tr>')
        if is_header:
            is_header = False
    html_out.append('</table>')
    return "".join(html_out)


def _format_ai_response_html(raw_text: str) -> str:
    if not raw_text:
        return ""
    
    # 1. Normalize excessive newlines (collapse multi-line gaps)
    text = raw_text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 2. Extract and format markdown tables
    lines = text.split('\n')
    out_lines = []
    in_table = False
    table_rows = []
    
    for line in lines:
        s_line = line.strip()
        if s_line.startswith('|') and s_line.endswith('|'):
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(s_line)
        else:
            if in_table:
                out_lines.append(_render_html_table(table_rows))
                in_table = False
                table_rows = []
            out_lines.append(line)
    if in_table:
        out_lines.append(_render_html_table(table_rows))
        
    formatted = '\n'.join(out_lines)
    
    # 3. Format headers (### / ## / #)
    formatted = re.sub(r'^(?:#{1,3})\s+(.+)$', r'<div style="font-weight:700;font-size:0.96rem;color:#f8fafc;margin:8px 0 3px;">\1</div>', formatted, flags=re.MULTILINE)
    
    # Numbered step emojis (1️⃣, 2️⃣, 3️⃣ or 1., 2.)
    formatted = re.sub(r'^([0-9]+[️⃣\.\)]\s*.+)$', r'<div style="font-weight:700;font-size:0.95rem;color:#c084fc;margin:8px 0 3px;">\1</div>', formatted, flags=re.MULTILINE)
    
    # 4. Bold text
    formatted = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#f1f5f9;">\1</strong>', formatted)
    
    # 5. Bullets
    formatted = re.sub(r'^[•\-\*]\s+(.+)$', r'<div style="margin:2px 0 2px 8px;color:#cbd5e1;display:flex;gap:6px;"><span style="color:#a855f7;">•</span><span>\1</span></div>', formatted, flags=re.MULTILINE)
    
    # 6. Paragraphs
    paragraphs = formatted.split('\n\n')
    p_html = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<div') or p.startswith('<table'):
            p_html.append(p)
        else:
            p_clean = p.replace('\n', '<br>')
            p_html.append(f'<div style="margin-bottom:6px;line-height:1.5;color:#cbd5e1;">{p_clean}</div>')
            
    return "".join(p_html)


# ──────────────────────────────────────────────────────────────────────────────
# Multi-Session Persistence & Database Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_sessions_file(data_dir: str) -> str:
    return os.path.join(data_dir or ".", "michael_sessions.json")


def _save_all_sessions(data_dir: str, data: dict) -> None:
    fp = _get_sessions_file(data_dir)
    try:
        tmp = fp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _mcj.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, fp)
    except Exception as e:
        print(f"[MICHAEL] Failed to save sessions: {e}", file=sys.stderr)


def _load_all_sessions(data_dir: str) -> dict:
    fp = _get_sessions_file(data_dir)
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = _mcj.load(f)
                if isinstance(data, dict) and "sessions" in data and data["sessions"]:
                    return data
        except Exception:
            pass

    # Migration from old single-session michael_chat.json if available
    old_fp = os.path.join(data_dir or ".", "michael_chat.json")
    migrated_messages = []
    if os.path.exists(old_fp):
        try:
            with open(old_fp, "r", encoding="utf-8") as f:
                old_msgs = _mcj.load(f)
                if isinstance(old_msgs, list) and old_msgs:
                    migrated_messages = old_msgs
        except Exception:
            pass

    now_iso = datetime.now().isoformat()
    default_session_id = f"session_{int(time.time())}_{_uuid.uuid4().hex[:6]}"
    default_title = "Initial Portfolio Briefing" if migrated_messages else "New Chat"

    new_data = {
        "active_session_id": default_session_id,
        "sessions": [
            {
                "id": default_session_id,
                "title": default_title,
                "created_at": now_iso,
                "updated_at": now_iso,
                "is_pinned": False,
                "messages": migrated_messages
            }
        ]
    }
    _save_all_sessions(data_dir, new_data)
    return new_data


def _create_new_session(data_dir: str, title: str = "New Chat") -> str:
    data = _load_all_sessions(data_dir)
    now_iso = datetime.now().isoformat()
    new_id = f"session_{int(time.time())}_{_uuid.uuid4().hex[:6]}"
    new_session = {
        "id": new_id,
        "title": title,
        "created_at": now_iso,
        "updated_at": now_iso,
        "is_pinned": False,
        "messages": []
    }
    data["sessions"].insert(0, new_session)
    data["active_session_id"] = new_id
    _save_all_sessions(data_dir, data)
    return new_id


def _get_active_session(data_dir: str) -> tuple[dict, dict]:
    data = _load_all_sessions(data_dir)
    if not data.get("sessions"):
        new_id = _create_new_session(data_dir)
        data = _load_all_sessions(data_dir)

    act_id = data.get("active_session_id")
    active_s = next((s for s in data["sessions"] if s["id"] == act_id), None)
    if not active_s:
        active_s = data["sessions"][0]
        data["active_session_id"] = active_s["id"]
        _save_all_sessions(data_dir, data)
    return active_s, data


def _rename_session(data_dir: str, session_id: str, new_title: str) -> None:
    data = _load_all_sessions(data_dir)
    for s in data.get("sessions", []):
        if s["id"] == session_id:
            s["title"] = new_title.strip() or "Untitled Chat"
            s["updated_at"] = datetime.now().isoformat()
            break
    _save_all_sessions(data_dir, data)


def _toggle_pin_session(data_dir: str, session_id: str) -> bool:
    data = _load_all_sessions(data_dir)
    new_pinned = False
    for s in data.get("sessions", []):
        if s["id"] == session_id:
            s["is_pinned"] = not s.get("is_pinned", False)
            s["updated_at"] = datetime.now().isoformat()
            new_pinned = s["is_pinned"]
            break
    _save_all_sessions(data_dir, data)
    return new_pinned


def _delete_session(data_dir: str, session_id: str) -> None:
    data = _load_all_sessions(data_dir)
    data["sessions"] = [s for s in data.get("sessions", []) if s["id"] != session_id]
    if not data["sessions"]:
        _create_new_session(data_dir)
    else:
        if data.get("active_session_id") == session_id:
            data["active_session_id"] = data["sessions"][0]["id"]
        _save_all_sessions(data_dir, data)


def _generate_auto_title(prompt: str) -> str:
    cleaned = prompt.strip().replace("\n", " ")
    for prefix in ["give me my", "give me", "can you", "what is", "tell me about", "analyze my", "show me", "please"]:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    if not cleaned:
        return "New Chat"
    title = cleaned[0].upper() + cleaned[1:]
    if len(title) > 34:
        title = title[:30].rsplit(" ", 1)[0] + "..."
    return title


def _group_sessions_by_date(sessions: list, search_filter: str = "") -> dict:
    if search_filter:
        s_term = search_filter.strip().lower()
        sessions = [
            s for s in sessions
            if s_term in s.get("title", "").lower()
            or any(s_term in m.get("text", "").lower() for m in s.get("messages", []))
        ]

    today = date.today()
    yesterday = today - timedelta(days=1)
    seven_days_ago = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)

    groups = {
        "Pinned": [],
        "Today": [],
        "Yesterday": [],
        "Previous 7 Days": [],
        "Previous 30 Days": [],
        "Older": []
    }

    for s in sessions:
        if s.get("is_pinned", False):
            groups["Pinned"].append(s)
            continue
        try:
            created_dt = datetime.fromisoformat(s.get("created_at", "").replace("Z", "+00:00")).date()
        except Exception:
            created_dt = today

        if created_dt == today:
            groups["Today"].append(s)
        elif created_dt == yesterday:
            groups["Yesterday"].append(s)
        elif created_dt >= seven_days_ago:
            groups["Previous 7 Days"].append(s)
        elif created_dt >= thirty_days_ago:
            groups["Previous 30 Days"].append(s)
        else:
            groups["Older"].append(s)

    return {k: v for k, v in groups.items() if v}


# ──────────────────────────────────────────────────────────────────────────────
# Main Render Function
# ──────────────────────────────────────────────────────────────────────────────

def render(df=None, summary=None, current_assets=None, _user_info=None,
           portfolio_sentiment_score=None, _sentiment_neg_count=None, comp_score=None):
    if df is None:
        df = pd.DataFrame()
    if summary is None:
        summary = {}
    if current_assets is None:
        current_assets = []

    total_invested = df['Invested (\u20b9)'].sum() if not df.empty and 'Invested (\u20b9)' in df.columns else 0.0
    total_pnl = df['P&L (\u20b9)'].sum() if not df.empty and 'P&L (\u20b9)' in df.columns else 0.0
    total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    try:
        total_val = summary.get('total_value', 0.0)
    except Exception:
        total_val = 0.0

    user_data_dir = st.session_state.get("_quest_data_dir", ".")

    # ── Custom CSS for ChatGPT-Style Layout ──────────────────────────────────
    st.markdown("""
    <style>
    /* Sticky Left Sidebar Layout */
    div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]) {
        align-items: flex-start !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
        position: sticky !important;
        top: 0.8rem !important;
        align-self: flex-start !important;
        z-index: 10 !important;
    }

    /* Clean custom scrollbar for containers */
    [data-testid="stContainer"], [data-testid="stVerticalBlock"] {
        scrollbar-width: thin !important;
        scrollbar-color: rgba(139, 92, 246, 0.3) transparent !important;
    }
    [data-testid="stContainer"]::-webkit-scrollbar, [data-testid="stVerticalBlock"]::-webkit-scrollbar {
        width: 5px !important;
    }
    [data-testid="stContainer"]::-webkit-scrollbar-thumb, [data-testid="stVerticalBlock"]::-webkit-scrollbar-thumb {
        background: rgba(139, 92, 246, 0.3) !important;
        border-radius: 4px !important;
    }
    [data-testid="stContainer"]::-webkit-scrollbar-thumb:hover, [data-testid="stVerticalBlock"]::-webkit-scrollbar-thumb:hover {
        background: rgba(168, 85, 247, 0.6) !important;
    }

    /* ChatGPT Layout Styles */
    .gpt-sidebar {
        background: rgba(13, 15, 28, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1rem;
        height: 100%;
        backdrop-filter: blur(16px);
    }
    .gpt-group-header {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #64748b;
        margin: 1.1rem 0 0.4rem 0.3rem;
    }
    .gpt-chat-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.6rem 0.8rem;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid transparent;
        margin-bottom: 0.35rem;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .gpt-chat-item:hover {
        background: rgba(255, 255, 255, 0.06);
        border-color: rgba(255, 255, 255, 0.1);
    }
    .gpt-chat-item.active {
        background: rgba(139, 92, 246, 0.16);
        border-color: rgba(168, 85, 247, 0.4);
        box-shadow: 0 0 15px rgba(139, 92, 246, 0.15);
    }
    .gpt-chat-title {
        font-size: 0.85rem;
        font-weight: 500;
        color: #f1f5f9;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
    }
    .gpt-chat-item.active .gpt-chat-title {
        color: #c084fc;
        font-weight: 600;
    }
    .gpt-chat-time {
        font-size: 0.68rem;
        color: #64748b;
        margin-left: 6px;
    }

    /* Main Chat Panel */
    .gpt-main-panel {
        background: rgba(10, 12, 22, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 18px;
        padding: 1.4rem;
        backdrop-filter: blur(20px);
        min-height: 650px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .gpt-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 0.9rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1.2rem;
    }
    .gpt-header-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .gpt-header-badge {
        font-size: 0.72rem;
        padding: 3px 8px;
        background: rgba(139, 92, 246, 0.2);
        border: 1px solid rgba(168, 85, 247, 0.35);
        border-radius: 12px;
        color: #c084fc;
        font-weight: 600;
    }

    /* Empty State Hero */
    .gpt-hero {
        text-align: center;
        padding: 2.5rem 1rem 1.5rem 1rem;
    }
    .gpt-hero-icon {
        width: 60px;
        height: 60px;
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.3), rgba(59, 130, 246, 0.4));
        border: 1px solid rgba(168, 85, 247, 0.45);
        box-shadow: 0 0 25px rgba(139, 92, 246, 0.35);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 2rem;
        margin-bottom: 1rem;
    }
    .gpt-hero-title {
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #f8fafc 0%, #cbd5e1 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.4rem;
    }
    .gpt-hero-subtitle {
        font-size: 0.9rem;
        color: #94a3b8;
        max-width: 480px;
        margin: 0 auto 2rem auto;
        line-height: 1.5;
    }
    .gpt-prompt-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        text-align: left;
        transition: all 0.25s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .gpt-prompt-card:hover {
        background: rgba(139, 92, 246, 0.08);
        border-color: rgba(168, 85, 247, 0.35);
        transform: translateY(-2px);
    }
    .gpt-card-title {
        font-size: 0.88rem;
        font-weight: 600;
        color: #f1f5f9;
        margin-bottom: 0.25rem;
    }
    .gpt-card-desc {
        font-size: 0.78rem;
        color: #94a3b8;
        line-height: 1.4;
    }

    /* Message Bubbles */
    .gpt-msg-user-row {
        display: flex;
        justify-content: flex-end;
        margin: 1rem 0;
    }
    .gpt-msg-user-bubble {
        background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
        color: #ffffff;
        padding: 0.85rem 1.2rem;
        border-radius: 18px 18px 4px 18px;
        max-width: 76%;
        font-size: 0.93rem;
        line-height: 1.55;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.25);
    }
    .gpt-msg-assistant-row {
        display: flex;
        justify-content: flex-start;
        margin: 1rem 0;
    }
    .gpt-msg-assistant-bubble {
        background: rgba(18, 20, 36, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 4px 18px 18px 18px;
        padding: 1rem 1.3rem;
        max-width: 84%;
        color: #cbd5e1;
        font-size: 0.93rem;
        line-height: 1.6;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .gpt-msg-meta {
        font-size: 0.68rem;
        color: #64748b;
        margin-top: 6px;
        font-family: "JetBrains Mono", monospace;
    }
    .gpt-disclaimer {
        font-size: 0.72rem;
        color: #475569;
        text-align: center;
        margin-top: 0.5rem;
    }
    .ti {
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 0.4rem 0.6rem;
    }
    .td {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #a855f7;
        animation: tb 1.2s infinite ease-in-out;
    }
    .td:nth-child(2) { animation-delay: .2s; }
    .td:nth-child(3) { animation-delay: .4s; }
    @keyframes tb {
        0%, 80%, 100% { transform: scale(.7); opacity: .5; }
        40% { transform: scale(1.1); opacity: 1; }
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Resolve Sessions ──────────────────────────────────────────────────────
    active_session, all_sessions_data = _get_active_session(user_data_dir)
    active_session_id = active_session["id"]
    messages = active_session.get("messages", [])

    # ── Provider & API Key resolution ─────────────────────────────────────────
    def _provider_of(k):
        return "groq" if str(k).startswith("gsk_") else "gemini"

    _shared_key = ""
    try:
        _shared_key = (str(st.secrets.get("GROQ_API_KEY", "")).strip()
                       or str(st.secrets.get("GEMINI_API_KEY", "")).strip())
    except Exception:
        _shared_key = ""

    if "michael_api_key" not in st.session_state:
        st.session_state.michael_api_key = ""
    if "michael_pending" not in st.session_state:
        st.session_state.michael_pending = None

    if _shared_key:
        api_key = _shared_key
        provider = _provider_of(_shared_key)
    else:
        api_key = st.session_state.michael_api_key.strip()
        provider = _provider_of(api_key) if api_key else "gemini"

    # ── Context builder (Compact target < 1000 tokens) ────────────────────────
    def _m_context():
        L = []
        L.append("=== PORTFOLIO SUMMARY ===")
        if not df.empty:
            tv = summary.get("total_value", 0)
            icol = "Invested (₹)" if "Invested (₹)" in df.columns else "Invested"
            pcol = "P&L (₹)" if "P&L (₹)" in df.columns else ("P&L" if "P&L" in df.columns else "P&L (%)")
            ppcol = "P&L %" if "P&L %" in df.columns else ("P&L (%)" if "P&L (%)" in df.columns else "")
            ti = df[icol].sum() if icol in df.columns else 0
            tp = df[pcol].sum() if pcol in df.columns else 0
            tpp = (tp / ti * 100) if ti > 0 else 0
            rs = summary.get("portfolio_risk_score", 0)
            rb = summary.get("portfolio_risk_bucket", "?")
            L += [
                f"Value: Rs.{tv:,.2f} | Invested: Rs.{ti:,.2f} | P&L: Rs.{tp:+,.2f} ({tpp:+.2f}%)",
                f"Risk: {rs:.1f}/100 ({rb})",
            ]
            if ppcol and ppcol in df.columns:
                sorted_df = df.sort_values(ppcol, ascending=False)
                top3 = sorted_df.head(3)
                bottom3 = sorted_df.tail(3)
                L.append("Top 3 gainers:")
                for _, r in top3.iterrows():
                    L.append(f"  {r.get('Name', 'Asset')}: {r.get(ppcol,0):+.2f}% (Rs.{r.get(pcol,0):+,.2f})")
                L.append("Top 3 losers:")
                for _, r in bottom3.iterrows():
                    L.append(f"  {r.get('Name', 'Asset')}: {r.get(ppcol,0):+.2f}% (Rs.{r.get(pcol,0):+,.2f})")
        else:
            L.append("No portfolio data yet.")

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

        L += ["", "=== RECENT PREDICTIONS (last 3) ==="]
        preds = get_predictions()
        for p in sorted(preds, key=lambda x: x["target_date"])[-3:]:
            act = f"Rs.{p['real_val']:,.2f}" if p.get("real_val") else "Pending"
            err = f"Rs.{(p['real_val']-p['expected_val']):+,.2f}" if p.get("real_val") else "-"
            L.append(f"  {p['target_date']} exp=Rs.{p['expected_val']:,.2f} act={act} err={err}")

        L += ["", "=== NEWS SENTIMENT ==="]
        try:
            from news_sentiment import get_archived_articles as _ga
            arch = _ga()
            for a in current_assets:
                if not getattr(a, 'identifier', None):
                    continue
                arts = [x for x in arch.get(a.identifier, []) if x.get("sentiment_score", 0) != 0]
                if arts:
                    sc = sum(x["sentiment_score"] for x in arts[:5]) / min(5, len(arts))
                    lb = "Bullish" if sc > 0.15 else "Bearish" if sc < -0.15 else "Neutral"
                    L.append(f"  {a.name}: {lb} ({sc:+.3f})")
        except Exception:
            L.append("News unavailable.")

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

        L += ["", "=== PLANNER (calendar + to-do) ==="]
        try:
            _mpd = st.session_state.get("_quest_data_dir", ".")
            try:
                with open(os.path.join(_mpd, "events.json"), encoding="utf-8") as _mf:
                    _m_evs = _mcj.load(_mf)
            except Exception:
                _m_evs = []
            try:
                with open(os.path.join(_mpd, "tasks.json"), encoding="utf-8") as _mf:
                    _m_tks = _mcj.load(_mf)
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

        return "\n".join(L)

    # ── AI API Drivers ────────────────────────────────────────────────────────
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
        _convo = ""
        for _hm in messages[-7:-1]:
            _convo += f"{'User' if _hm.get('role') == 'user' else 'MICHAEL'}: {_hm.get('text','')}\n"
        full = f"{SYS}\n\n--- CONTEXT ---\n{ctx}\n--- END ---\n\n{_convo}User: {q}\nMICHAEL:"
        payload = _j.dumps({
            "contents": [{"parts": [{"text": full}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }).encode()

        models_to_try = [st.session_state["_michael_model"]] if "_michael_model" in st.session_state else _GEMINI_MODELS
        last_error = "No models attempted."
        for model in models_to_try:
            url = f"{_GEMINI_BASE}/{model}:generateContent?key={key}"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    res = _j.loads(r.read().decode())
                st.session_state["_michael_model"] = model
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                if e.code in (400, 403):
                    return "__BAD_KEY__"
                last_error = f"HTTP {e.code}: {body[:400]}"
                continue
            except Exception as ex:
                last_error = str(ex)
                continue
        return f"__RATE_LIMIT__ {last_error}"

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
                        sym = q2["symbol"]
                        break
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
            _d = h.diff()
            _up = _d.clip(lower=0).rolling(14).mean()
            _dn = (-_d.clip(upper=0)).rolling(14).mean()
            _rs = _up / _dn.replace(0, float('nan'))
            rsi = float((100 - 100 / (1 + _rs)).iloc[-1])
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
            last = float(fi.last_price)
            prev = float(fi.previous_close)
            return _J.dumps({"index": name, "value": round(last, 2),
                             "day_change_pct": round((last - prev) / prev * 100, 2)})
        except Exception as e:
            return _J.dumps({"error": str(e)})

    _TOOLS = [
        {"type": "function", "function": {
            "name": "get_quote",
            "description": "Get LIVE price and technical indicators (RSI, 50/200 trend, 52-week range, 6-month return) for ANY Indian stock.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Company name or ticker, e.g. 'Reliance' or 'TCS.NS'"}},
                "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "get_index",
            "description": "Get live value and day change for an Indian market index (NIFTY 50, SENSEX, Bank Nifty).",
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
            "(events + to-dos). You ALSO have live tools: get_quote and get_index. ALWAYS call get_quote or get_index when asked about a "
            "specific stock, index, or recommendations. "
            "PERSONALITY: a sharp, seasoned Mumbai trading-desk veteran — quick-witted, a little blunt, dry humour, "
            "genuinely in the user's corner. Open with one short line fitting the time of day and market mood, then "
            "get straight to the point. Direct and honest. Ground every answer in the data/tools. "
            "Concise, short paragraphs, Rs. for rupees, plain text (no markdown headers)."
        )
        msgs = [{"role": "system", "content": SYS + "\n\n--- CONTEXT ---\n" + ctx + "\n--- END ---"}]
        for _hm in messages[-7:-1]:
            msgs.append({"role": "user" if _hm.get("role") == "user" else "assistant", "content": _hm.get("text", "")})
        msgs.append({"role": "user", "content": q})
        H = {"Content-Type": "application/json", "Authorization": f"Bearer {key}",
             "User-Agent": "Mozilla/5.0"}

        def _post(messages_list, use_tools=True):
            body = {"model": "openai/gpt-oss-120b", "messages": messages_list, "temperature": 0.6, "max_tokens": 1024}
            if use_tools:
                body["tools"] = _TOOLS
                body["tool_choice"] = "auto"
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                                         data=_j.dumps(body).encode(), headers=H, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                return _j.loads(r.read().decode())

        try:
            m = {}
            for _round in range(12):
                import time as _time
                try:
                    res = _post(msgs, use_tools=True)
                except urllib.error.HTTPError as _te:
                    _tb = _te.read().decode("utf-8", errors="ignore")
                    if _te.code == 429:
                        m_wait = re.search(r"try again in ([\d\.]+)s", _tb)
                        wait_t = float(m_wait.group(1)) + 1.0 if m_wait else 8.0
                        _time.sleep(wait_t)
                        res = _post(msgs, use_tools=True)
                    elif _te.code == 400 and "tool_use_failed" in _tb:
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
                    msgs.append({"role": "tool", "tool_call_id": tc.get("id"), "content": out})
            return (m.get("content") or "I pulled the data but ran out of steps — ask me once more.").strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            if e.code in (401, 403):
                return "__BAD_KEY__"
            return f"__RATE_LIMIT__ HTTP {e.code}: {body[:300]}"
        except Exception as ex:
            return f"__RATE_LIMIT__ {ex}"

    def _m_ask(q, ctx):
        return _m_groq(api_key, q, ctx) if provider == "groq" else _m_gemini(api_key, q, ctx)

    # ── Send and Process Message ──────────────────────────────────────────────
    def _m_send(q_text):
        if not q_text.strip():
            return
        ts = datetime.now().strftime("%H:%M")
        
        # If this is the first message in a default 'New Chat', auto-rename session
        if active_session.get("title") in ["New Chat", "Untitled Chat"] and not messages:
            new_title = _generate_auto_title(q_text)
            _rename_session(user_data_dir, active_session_id, new_title)
            active_session["title"] = new_title

        active_session.setdefault("messages", []).append({"role": "user", "text": q_text.strip(), "ts": ts})
        active_session["updated_at"] = datetime.now().isoformat()
        _save_all_sessions(user_data_dir, all_sessions_data)
        st.session_state.michael_pending = q_text.strip()

    def _m_process():
        q = st.session_state.michael_pending
        if not q:
            return
        st.session_state.michael_pending = None
        raw = _m_ask(q, _m_context())
        ts = datetime.now().strftime("%H:%M")
        if raw == "__BAD_KEY__":
            txt = ("MICHAEL is unavailable — the API key is invalid or not authorised. "
                   "Check the key in the app's secrets or settings.")
        elif raw.startswith("__RATE_LIMIT__"):
            detail = raw[len("__RATE_LIMIT__"):].strip()
            txt = f"MICHAEL hit a temporary API rate limit. Please give it a moment and try again.\n\nDetails: {detail}"
        else:
            txt = raw

        active_session.setdefault("messages", []).append({"role": "michael", "text": txt, "ts": ts})
        active_session["updated_at"] = datetime.now().isoformat()
        _save_all_sessions(user_data_dir, all_sessions_data)

    # ──────────────────────────────────────────────────────────────────────────
    # ChatGPT Split Layout (Left Sidebar + Right Main Chat)
    # ──────────────────────────────────────────────────────────────────────────
    col_sidebar, col_main = st.columns([1.1, 3.2], gap="medium")

    # ══════════════════════════════════════════════════════════════════════════
    # Left Column: Chat History Sidebar (Fixed in place)
    # ══════════════════════════════════════════════════════════════════════════
    with col_sidebar:
        # + New Chat Button (Fixed at top of sidebar)
        if st.button("➕  New Chat", key="btn_new_chat", type="primary", use_container_width=True):
            new_sid = _create_new_session(user_data_dir)
            st.rerun()

        st.markdown("<div style='margin-bottom: 0.35rem;'></div>", unsafe_allow_html=True)
        # Search Bar (Fixed at top of sidebar)
        search_query = st.text_input("Search chats", placeholder="🔍 Search conversations...",
                                     label_visibility="collapsed", key="search_chat_input")

        # Scrollable conversation list container (sidebar itself stays fixed)
        with st.container(height=520, border=False):
            grouped = _group_sessions_by_date(all_sessions_data.get("sessions", []), search_query)

            if not grouped:
                st.markdown("<div style='font-size:0.8rem;color:#64748b;text-align:center;padding:1.5rem 0;'>No conversations found.</div>", unsafe_allow_html=True)
            else:
                for grp_name, s_list in grouped.items():
                    st.markdown(f'<div class="gpt-group-header">{grp_name}</div>', unsafe_allow_html=True)
                    for s in s_list:
                        s_id = s["id"]
                        is_active = (s_id == active_session_id)
                        s_title = s.get("title", "Untitled Chat")
                        is_pin = s.get("is_pinned", False)

                        # Chat card button row
                        c_btn, c_opt = st.columns([4, 1])
                        with c_btn:
                            btn_label = f"{'📌 ' if is_pin and grp_name != 'Pinned' else ''}{s_title}"
                            if st.button(btn_label, key=f"sel_chat_{s_id}",
                                         type="primary" if is_active else "secondary",
                                         use_container_width=True):
                                all_sessions_data["active_session_id"] = s_id
                                _save_all_sessions(user_data_dir, all_sessions_data)
                                st.rerun()

                        with c_opt:
                            with st.popover("⚙", use_container_width=True):
                                st.markdown(f"**{s_title}**")
                                # Pin / Unpin
                                pin_txt = "📌 Unpin chat" if is_pin else "📌 Pin chat to top"
                                if st.button(pin_txt, key=f"pin_btn_{s_id}", use_container_width=True):
                                    _toggle_pin_session(user_data_dir, s_id)
                                    st.rerun()

                                # Rename Form
                                with st.form(key=f"rename_form_{s_id}"):
                                    new_t = st.text_input("Rename title", value=s_title, key=f"rename_input_{s_id}")
                                    if st.form_submit_button("Save Title", use_container_width=True):
                                        if new_t.strip():
                                            _rename_session(user_data_dir, s_id, new_t)
                                            st.rerun()

                                # Delete Chat
                                if st.button("🗑️ Delete Chat", key=f"del_btn_{s_id}", type="secondary", use_container_width=True):
                                    _delete_session(user_data_dir, s_id)
                                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # Right Column: ChatGPT Main Conversational Panel
    # ══════════════════════════════════════════════════════════════════════════
    with col_main:
        # Header bar
        header_title = active_session.get("title", "New Chat")
        is_active_pinned = active_session.get("is_pinned", False)
        provider_badge = f"⚡ {provider.upper()} (gpt-oss-120b)" if provider == "groq" else f"⚡ {provider.upper()}"

        h_col1, h_col2 = st.columns([3, 1])
        with h_col1:
            pin_badge_html = ' <span style="font-size:0.85rem;color:#facc15;">📌</span>' if is_active_pinned else ''
            st.markdown(f'<div class="gpt-header-title">{header_title}{pin_badge_html}</div>', unsafe_allow_html=True)
        with h_col2:
            st.markdown(f'<div style="text-align:right;"><span class="gpt-header-badge">{provider_badge}</span></div>', unsafe_allow_html=True)

        st.markdown("<hr style='margin: 0.35rem 0 0.8rem 0; border-color: rgba(255,255,255,0.08);'>", unsafe_allow_html=True)

        # ── Dedicated Scrollable Message Viewport ─────────────────────────────
        msg_container = st.container(height=520, border=False, autoscroll=True)
        with msg_container:
            if not messages:
                # Polished Empty State Hero & 4 Financial Starter Cards
                st.markdown("""
                <div class="gpt-hero">
                    <div class="gpt-hero-icon">⚡</div>
                    <div class="gpt-hero-title">How can I help with your portfolio today?</div>
                    <div class="gpt-hero-subtitle">I have real-time access to your holdings, risk analytics, news sentiment, EWMA predictions, and planner.</div>
                </div>
                """, unsafe_allow_html=True)

                card_col1, card_col2 = st.columns(2, gap="medium")
                with card_col1:
                    st.markdown("""
                    <div class="gpt-prompt-card">
                        <div class="gpt-card-title">📊 Daily Briefing</div>
                        <div class="gpt-card-desc">Comprehensive morning market summary and portfolio P&L review.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Ask: Give me my daily briefing", key="chip_briefing", use_container_width=True):
                        _m_send("Give me my daily briefing")
                        st.rerun()

                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

                    st.markdown("""
                    <div class="gpt-prompt-card">
                        <div class="gpt-card-title">📅 Planner & Tasks</div>
                        <div class="gpt-card-desc">Check upcoming corporate results, holidays, and open to-do items.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Ask: What's on my plate today?", key="chip_planner", use_container_width=True):
                        _m_send("What's on my plate today?")
                        st.rerun()

                with card_col2:
                    st.markdown("""
                    <div class="gpt-prompt-card">
                        <div class="gpt-card-title">🛡️ Risk & Moats</div>
                        <div class="gpt-card-desc">Analyze portfolio concentration, volatility, and downside risk score.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Ask: Analyze my portfolio risk", key="chip_risk", use_container_width=True):
                        _m_send("Analyze my portfolio risk & asset allocation")
                        st.rerun()

                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

                    st.markdown("""
                    <div class="gpt-prompt-card">
                        <div class="gpt-card-title">🔍 Underperformers</div>
                        <div class="gpt-card-desc">Identify which assets are dragging down returns and check news catalysts.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Ask: Which stock is dragging returns?", key="chip_draggers", use_container_width=True):
                        _m_send("Which stock is dragging down my returns?")
                        st.rerun()

            else:
                # Render message stream
                for msg in messages:
                    if msg["role"] == "user":
                        clean_u_text = html.escape(msg["text"]).replace('\n', '<br>')
                        st.markdown(
                            f'<div class="gpt-msg-user-row">'
                            f'<div class="gpt-msg-user-bubble">{clean_u_text}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        fmt_m_text = _format_ai_response_html(msg["text"])
                        ts_val = msg.get("ts", "")
                        st.markdown(
                            f'<div class="gpt-msg-assistant-row">'
                            f'<div class="gpt-msg-assistant-bubble">'
                            f'<div style="font-weight:700;color:#c084fc;font-size:0.8rem;margin-bottom:6px;letter-spacing:0.5px;">⚡ MICHAEL</div>'
                            f'{fmt_m_text}'
                            f'<div class="gpt-msg-meta">{ts_val}</div>'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                # Typing / Generating indicator
                if st.session_state.michael_pending:
                    st.markdown("""
                    <div class="gpt-msg-assistant-row">
                        <div class="gpt-msg-assistant-bubble">
                            <div style="font-weight:700;color:#c084fc;font-size:0.8rem;margin-bottom:6px;">⚡ MICHAEL</div>
                            <div class="ti">
                                <div class="td"></div><div class="td"></div><div class="td"></div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # Process pending AI query
        if st.session_state.michael_pending:
            _m_process()
            st.rerun()

        # ── ChatGPT Fixed Bottom Input Bar ────────────────────────────────────
        st.markdown("<div style='margin-top: 0.8rem;'></div>", unsafe_allow_html=True)
        with st.form("gpt_input_form", clear_on_submit=True):
            input_c1, input_c2 = st.columns([5.2, 1])
            with input_c1:
                user_msg = st.text_input("Message MICHAEL", key="gpt_chat_input",
                                         placeholder="Message MICHAEL (e.g., 'What is my portfolio risk today?')...",
                                         label_visibility="collapsed")
            with input_c2:
                btn_send = st.form_submit_button("Send ⚡", use_container_width=True)

        if btn_send and user_msg.strip():
            _m_send(user_msg)
            st.rerun()

        st.markdown("""
        <div class="gpt-disclaimer">
            MICHAEL is an AI portfolio intelligence assistant. Verify financial calculations and decisions with qualified advisors.
        </div>
        """, unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════════════════
    # PLANNER — editable calendar + to-do (Overview keeps a read-only quick glance)
    # ══════════════════════════════════════════════════════════════════════════════
