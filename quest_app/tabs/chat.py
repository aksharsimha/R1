import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import datetime as _dt
import plotly.express as px
import plotly.graph_objects as go
import time
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings
import chat_system
import nse_live as _nse
import html



def _get_profile_cached(username: str) -> dict:
    if not username:
        return {}
    if "_user_profiles_cache" not in st.session_state:
        st.session_state._user_profiles_cache = {}
    if username not in st.session_state._user_profiles_cache:
        try:
            import firebase_db
            prof = firebase_db.get_user_profile(username)
            st.session_state._user_profiles_cache[username] = prof or {}
        except Exception:
            st.session_state._user_profiles_cache[username] = {}
    return st.session_state._user_profiles_cache.get(username, {})


def _render_avatar_html(username: str, display_name: str = "", size: int = 54, css_class: str = "chat-avatar") -> str:
    prof = _get_profile_cached(username) if username else {}
    av = prof.get("avatar")
    disp = prof.get("display_name") or display_name or username or "User"
    if av:
        return f'<img src="{av}" class="{css_class}" style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;" alt="{disp}">'
    else:
        init = disp[:1].upper() if disp else "?"
        font_size = max(11, int(size * 0.44))
        return f'<div class="{css_class}" style="width:{size}px;height:{size}px;border-radius:50%;display:grid;place-items:center;font-size:{font_size}px;font-weight:600;">{init}</div>'


@st.dialog("Profile Card", width="small")
def _show_public_profile(username: str):
    st.markdown("""
    <style>
    div[data-testid="stDialog"] div[data-testid="stDialogHeader"] {
        padding-bottom: 4px !important;
    }
    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"] {
        padding: 0 !important;
        gap: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    import quest_app.settings as settings
    profile = _get_profile_cached(username)
    card_html = settings.build_discord_profile_card_html(username, profile)
    st.html(card_html)



@st.dialog("New conversation")
def _new_conversation_dialog(username: str):
    friend_names = chat_system.get_friends(username)
    if not friend_names:
        st.info("Add a friend before starting a conversation.")
        return
    with st.form("new_conversation_form"):
        friend = st.selectbox("Choose a friend", friend_names)
        if st.form_submit_button("Open conversation", type="primary"):
            st.session_state.active_chat_id = chat_system.get_or_create_dm(username, friend)
            st.rerun(scope="fragment")

@st.fragment
def render(df=None, summary=None, current_assets=None, _user_info=None,
           portfolio_sentiment_score=None, _sentiment_neg_count=None, comp_score=None):
    if "chat_id" in st.query_params:
        st.session_state.active_chat_id = st.query_params["chat_id"]

    if "view_profile" in st.query_params:
        target_user = st.query_params["view_profile"]
        del st.query_params["view_profile"]
        _show_public_profile(target_user)

    total_invested = df['Invested (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl = df['P&L (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    try:
        total_val = summary['total_value']
    except Exception:
        total_val = 0.0
    _chat_user = _user_info["username"]
    _chat_display = _user_info["display_name"]
    import firebase_db
    firebase_db.set_user_presence(_chat_user)

    # ── Chat CSS ─────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
        .chat-shell {
            background: var(--q-surface);
            border: 1px solid var(--q-border);
            border-radius: 14px;
            padding: 14px;
            min-height: 610px;
            box-shadow: 0 18px 45px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.04);
        }
        .chat-rail {
            background: var(--q-surface-2);
            border-right: 1px solid var(--q-border);
            border-radius: 12px 0 0 12px;
            min-height: 580px;
            padding: 12px 10px;
        }
        .chat-title { color: var(--q-text); font-size: 1.25rem; font-weight: 600; margin: 4px 0 18px; }
        .chat-title-icon { color: var(--q-accent); margin-right: 7px; }
        .chat-header { display:flex; align-items:center; gap:14px; border-bottom:1px solid var(--q-border); padding:2px 4px 16px; }
        .chat-avatar-link {
            text-decoration: none !important;
            cursor: pointer !important;
            display: inline-flex;
            flex-shrink: 0;
            border-radius: 50%;
            transition: transform 0.2s cubic-bezier(.22,.61,.36,1), box-shadow 0.2s cubic-bezier(.22,.61,.36,1);
        }
        .chat-avatar-link:hover {
            transform: scale(1.06);
        }
        .chat-avatar-link:hover .chat-avatar {
            border-color: var(--q-accent) !important;
            box-shadow: 0 0 14px rgba(93, 202, 165, 0.45), 0 0 0 4px rgba(93, 202, 165, 0.2) !important;
        }
        .chat-avatar-wrap { position:relative; display:inline-flex; flex-shrink:0; width:54px; height:54px; }
        .chat-avatar { width:54px; height:54px; border-radius:50%; object-fit:cover; display:grid; place-items:center; background:var(--q-surface-2); border:2px solid var(--q-border); color:var(--q-text-2); font-size:1.55rem; box-shadow:0 0 0 4px rgba(69,78,106,.18); flex-shrink:0; transition: all 0.2s ease; }
        .chat-online { width:14px; height:14px; border-radius:50%; background:var(--q-pos); border:2px solid var(--q-surface); position:absolute; bottom:0; right:0; z-index:2; }
        .chat-name-link {
            text-decoration: none !important;
            color: inherit !important;
            cursor: pointer !important;
            display: inline-block;
            transition: color 0.2s ease, transform 0.2s ease;
        }
        .chat-name-link:hover .chat-header-name {
            color: var(--q-accent) !important;
            text-decoration: none;
        }
        .chat-name-link:hover {
            transform: translateX(1px);
        }
        .chat-header-name { color:var(--q-text); font-size:1.25rem; font-weight:600; transition: color 0.2s ease; }
        .chat-header-status { color:var(--q-text-3); font-size:.78rem; margin-top:2px; }
        .chat-header-status span { color:var(--q-pos); }
        /* Hidden profile trigger slot (zero visual presence) */
        .st-key-chat_hdr_prof_slot,
        div[class*="st-key-chat_hdr_prof_slot"] {
            position: absolute !important;
            top: -9999px !important;
            left: -9999px !important;
            width: 1px !important;
            height: 1px !important;
            min-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        .chat-empty { min-height:470px; display:grid; place-items:center; color:var(--q-text-3); text-align:center; }
        .chat-rail .stButton > button { border-color:var(--q-border); background:var(--q-surface); }
        .chat-rail .stButton > button:hover { border-color:var(--q-accent); background:var(--q-accent-weak); }
        .chat-action { border:1px solid var(--q-accent); border-radius:10px; padding:11px 12px; color:var(--q-text-2); background:var(--q-surface-2); margin:10px 0; }
        .chat-action strong { color:var(--q-text); font-size:.86rem; }
        .chat-action small { display:block; color:var(--q-text-3); margin-top:2px; }
        @media (max-width: 760px) {
            .chat-shell { padding:8px; min-height:0; }
            .chat-rail { min-height:0; border-right:0; border-bottom:1px solid var(--q-border); border-radius:10px; }
            .chat-header-name { font-size:1.05rem; }
        }
        .chat-msg-row { display: flex; margin-bottom: 12px; align-items: flex-end; }
        .chat-msg-row.sent { justify-content: flex-end; }
        .chat-msg-row.received { justify-content: flex-start; }
        .chat-msg-row.system-row { justify-content: center; }
        .chat-msg-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            object-fit: cover;
            border: 1.5px solid var(--q-border);
            flex-shrink: 0;
            display: grid;
            place-items: center;
            background: var(--q-surface-2);
            color: var(--q-text-2);
            font-size: 0.85rem;
            font-weight: 600;
        }
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
        /* Keep Streamlit's generated input anchored while the message list scrolls. */
        [data-testid="stChatInput"] {
            position: sticky !important;
            bottom: 0;
            z-index: 20;
            background: var(--q-surface, transparent);
        }
    </style>
    """, unsafe_allow_html=True)

    # ── Session state init ───────────────────────────────────────────────────
    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = None

    # ── Layout: sidebar + chat area ──────────────────────────────────────────
    chat_sidebar, chat_main = st.columns([1, 2.5])

    with chat_sidebar:
        _conversation_title, _compose = st.columns([5, 1])
        _conversation_title.markdown("<div class='chat-title'><span class='chat-title-icon'>♣</span>Conversations</div>", unsafe_allow_html=True)
        if _compose.button("✎", key="new_conversation", help="New conversation"):
            _new_conversation_dialog(_chat_user)

        # ── Friend Requests ──────────────────────────────────────────────────
        pending = chat_system.get_friend_requests(_chat_user)
        if pending:
            with st.expander(f"📨 Friend Requests ({len(pending)})", expanded=True):
                for req_from in pending:
                    rc1, rc2, rc3 = st.columns([2, 1, 1])
                    rc1.markdown(f"**{req_from}**")
                    if rc2.button("✓", key=f"acc_{req_from}", help="Accept"):
                        chat_system.accept_friend_request(_chat_user, req_from)
                        st.rerun(scope="fragment")
                    if rc3.button("✗", key=f"dec_{req_from}", help="Decline"):
                        chat_system.decline_friend_request(_chat_user, req_from)
                        st.rerun(scope="fragment")

        # ── Chat list ────────────────────────────────────────────────────────
        user_chats = chat_system.get_user_chats(_chat_user)

        _chat_search = st.text_input("Search conversations", placeholder="Search by name", key="chat_search", label_visibility="collapsed")
        _visible_chats = [chat_info for chat_info in user_chats if not _chat_search.strip() or _chat_search.strip().lower() in chat_info["display_name"].lower()]
        if _visible_chats:
            for chat_info in _visible_chats:
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
                    st.rerun(scope="fragment")
        elif user_chats:
            st.caption("No conversations match your search.")
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
                        st.rerun(scope="fragment")

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
                            st.rerun(scope="fragment")

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
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:400px;color:var(--q-text-3);">
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
                hdr0, hdr_main, hdr_action, hdr_refresh = st.columns([0.6, 4.8, 2.0, 0.6])
                with hdr0:
                    if st.button("←", key="chat_back", help="Back to conversations"):
                        st.session_state.active_chat_id = None
                        st.rerun(scope="fragment")
                with hdr_main:
                    if chat_info["type"] == "direct":
                        other = [p for p in chat_info["participants"] if p != _chat_user]
                        other_user = other[0] if other else ""
                        other_prof = _get_profile_cached(other_user) if other_user else {}
                        title = other_prof.get("display_name") or other_user or "Chat"
                        _is_online = firebase_db.is_user_online(other_user) if other_user else False
                        _avatar_markup = _render_avatar_html(other_user, title, size=46, css_class="chat-avatar")
                        _profile_target = other_user
                    else:
                        title = chat_info["name"]
                        members_str = ", ".join(chat_info["participants"])
                        _is_online = False
                        _avatar_markup = "<div class='chat-avatar' style='font-size:1.3rem;width:46px;height:46px;border-radius:50%;display:grid;place-items:center;'>👥</div>"
                        _profile_target = ""

                    _presence_label = "Online" if _is_online else "Offline"
                    _presence_color = "var(--q-pos)" if _is_online else "var(--q-text-3)"
                    _presence_dot = "<div class='chat-online'></div>" if _is_online else ""
                    _target_tag = f"<span style='color:var(--q-text-3);margin-right:6px;'>@{html.escape(_profile_target)}</span>" if _profile_target else ""

                    st.markdown(f"""
                    <div style='display:flex;align-items:center;gap:12px;'>
                        <div class='chat-avatar-wrap' style='position:relative;flex-shrink:0;'>{_avatar_markup}{_presence_dot}</div>
                        <div style='overflow:hidden;'>
                            <div class='chat-header-name' style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{html.escape(title)}</div>
                            <div class='chat-header-status' style='font-size:0.78rem;'>
                                {_target_tag}
                                Status: <span style='color:{_presence_color};font-weight:600;'>{_presence_label}</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with hdr_action:
                    if chat_info["type"] == "direct" and _profile_target:
                        if st.button("👤 Profile Card", key=f"chat_view_prof_btn_{active_id}", help=f"View {_profile_target}'s Profile Card", use_container_width=True):
                            _show_public_profile(_profile_target)
                    elif chat_info["type"] == "group":
                        with st.popover("👥 Members", use_container_width=True):
                            st.markdown(f"**{chat_info['name']}**")
                            st.caption(f"{len(chat_info['participants'])} members in this group")
                            for p in chat_info["participants"]:
                                p_prof = _get_profile_cached(p)
                                p_disp = p_prof.get("display_name", p)
                                c_p1, c_p2 = st.columns([3, 2])
                                with c_p1:
                                    st.markdown(f"**{p_disp}**<br><span style='font-size:0.75rem;color:var(--q-text-3);'>@{p}</span>", unsafe_allow_html=True)
                                with c_p2:
                                    if st.button("Profile", key=f"grp_prof_btn_{p}_{active_id}", use_container_width=True):
                                        _show_public_profile(p)

                with hdr_refresh:
                    if st.button("🔄", key="chat_refresh", help="Refresh messages & avatars"):
                        st.session_state.pop("_user_profiles_cache", None)
                        st.rerun(scope="fragment")

                _share_col, _share_hint = st.columns([1, 5])
                if _share_col.button("📊", key="share_portfolio", help="Share portfolio"):
                    snapshot = chat_system.build_portfolio_snapshot(df, summary, _chat_user)
                    text = f"📊 Portfolio Snapshot from {_chat_display}"
                    chat_system.send_message(
                        active_id, _chat_user, text,
                        msg_type="portfolio_share",
                        portfolio_data=snapshot,
                    )
                    st.session_state.chat_scroll_to_latest = True
                    st.rerun(scope="fragment")
                _share_hint.caption("Share a portfolio snapshot with this conversation.")

                st.markdown("<div style='height:1px;background:var(--q-border);margin:0 0 12px;'></div>", unsafe_allow_html=True)

                # ── Messages ─────────────────────────────────────────────────
                messages = chat_system.get_messages(active_id, limit=100)
                force_scroll = st.session_state.pop("chat_scroll_to_latest", False)
                message_version = messages[-1].get("id") or messages[-1].get("timestamp", "") if messages else "empty"

                if not messages:
                    st.markdown("<div class='chat-empty'><div><div style='font-size:2.5rem;'>◌</div><div>No messages yet</div><small>Say hello to start the conversation.</small></div></div>", unsafe_allow_html=True)
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
                            my_av_markup = _render_avatar_html(_chat_user, _chat_display, size=32, css_class="chat-msg-avatar")
                            bubble = f'<div class="chat-bubble sent">{msg["text"]}'
                            if msg.get("type") == "portfolio_share" and msg.get("portfolio_data"):
                                pd_data = msg["portfolio_data"]
                                pnl_color = "var(--q-pos)" if pd_data.get("total_pnl", 0) >= 0 else "var(--q-neg)"
                                bubble += f"""
                                <div class="portfolio-card">
                                    <h4>📊 {pd_data.get('username', 'User')}'s Portfolio</h4>
                                    <div class="label">Value</div>
                                    <div class="val">₹{pd_data.get('total_value', 0):,.2f}</div>
                                    <div class="label" style="margin-top:6px;">P&L</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('pnl_pct', 0):+.1f}%</div>
                                    <div class="label" style="margin-top:6px;">Growth</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('growth_abs', 0):+,.0f}</div>
                                </div>"""
                            bubble += f'<div class="chat-time">{time_str}</div></div>'
                            msgs_html += f'<div class="chat-msg-row sent">{bubble}<div style="margin-left:8px;flex-shrink:0;">{my_av_markup}</div></div>'
                        else:
                            # ── Received message ─────────────────────────────
                            sender = msg["from"]
                            sender_prof = _get_profile_cached(sender)
                            sender_disp = sender_prof.get("display_name", sender)
                            sender_av_markup = _render_avatar_html(sender, sender_disp, size=32, css_class="chat-msg-avatar")
                            _sender_header = f'<div class="chat-sender">{html.escape(sender_disp)} <span style="font-size:0.75rem;color:var(--q-text-3);font-weight:400;">(@{html.escape(sender)})</span></div>'

                            bubble = f'<div class="chat-bubble received">{_sender_header}{msg["text"]}'
                            if msg.get("type") == "portfolio_share" and msg.get("portfolio_data"):
                                pd_data = msg["portfolio_data"]
                                pnl_color = "var(--q-pos)" if pd_data.get("total_pnl", 0) >= 0 else "var(--q-neg)"
                                bubble += f"""
                                <div class="portfolio-card">
                                    <h4>📊 {pd_data.get('username', 'User')}'s Portfolio</h4>
                                    <div class="label">Value</div>
                                    <div class="val">₹{pd_data.get('total_value', 0):,.2f}</div>
                                    <div class="label" style="margin-top:6px;">P&L</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('pnl_pct', 0):+.1f}%</div>
                                    <div class="label" style="margin-top:6px;">Growth</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('growth_abs', 0):+,.0f}</div>
                                </div>"""
                            bubble += f'<div class="chat-time">{time_str}</div></div>'
                            msgs_html += f'<div class="chat-msg-row received"><div style="margin-right:8px;flex-shrink:0;">{sender_av_markup}</div>{bubble}</div>'

                    st.html(f'''
                    <div id="quest-chat-messages" data-chat-id="{active_id}"
                        data-force-scroll="{'true' if force_scroll else 'false'}"
                        data-message-version="{message_version}"
                         style="max-height:450px;overflow-y:auto;padding:8px 0;">
                        {msgs_html}
                    </div>
                    <script>
                    (function() {{
                        var container = document.getElementById('quest-chat-messages');
                        if (!container) return;

                        var chatId = container.getAttribute('data-chat-id');
                        var stateKey = 'quest-chat-scroll:' + chatId;
                        var versionKey = stateKey + ':version';
                        var openedChatKey = 'quest-chat-open';
                        var messageVersion = container.getAttribute('data-message-version') || '';
                        var nearBottom = function() {{
                            return container.scrollHeight - container.scrollTop - container.clientHeight < 48;
                        }};
                        var forceScroll = container.getAttribute('data-force-scroll') === 'true';
                        var firstRender = sessionStorage.getItem(versionKey) === null;
                        var openedChat = sessionStorage.getItem(openedChatKey) !== chatId;
                        var messageChanged = sessionStorage.getItem(versionKey) !== messageVersion;
                        var followLatest = forceScroll || openedChat || sessionStorage.getItem(stateKey) !== 'away';

                        var rememberPosition = function() {{
                            var atBottom = nearBottom();
                            sessionStorage.setItem(stateKey, atBottom ? 'bottom' : 'away');
                            followLatest = atBottom;
                        }};
                        container.addEventListener('scroll', rememberPosition, {{ passive: true }});

                        var scrollLatest = function() {{
                            if (!followLatest) return;
                            container.scrollTop = container.scrollHeight;
                        }};

                        requestAnimationFrame(function() {{
                            if (firstRender || (messageChanged && followLatest)) scrollLatest();
                            sessionStorage.setItem(openedChatKey, chatId);
                            sessionStorage.setItem(versionKey, messageVersion);
                            if (firstRender || (messageChanged && followLatest)) sessionStorage.setItem(stateKey, 'bottom');
                        }});

                        if (window.ResizeObserver) {{
                            var resizeObserver = new ResizeObserver(function() {{
                                if (followLatest) scrollLatest();
                            }});
                            resizeObserver.observe(container);
                        }}
                    }})();
                    </script>
                    ''', unsafe_allow_javascript=True)

                # ── Message input ────────────────────────────────────────────
                new_msg = st.chat_input(
                    "Type a message...",
                    key="chat_msg_input",
                )
                if new_msg and new_msg.strip():
                    sent, _ = chat_system.send_message(active_id, _chat_user, new_msg)
                    if sent:
                        st.session_state.chat_scroll_to_latest = True
                        st.rerun(scope="fragment")

    # =============================================================================
    # ⚡ MICHAEL TAB (AI Chat Assistant)
    # =============================================================================
