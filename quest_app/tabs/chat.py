import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
import plotly.express as px
import plotly.graph_objects as go
import time
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings
import chat_system
import nse_live as _nse


@st.dialog("Public Profile")
def _show_public_profile(username: str):
    import firebase_db
    profile = firebase_db.get_user_profile(username)
    if profile:
        av = profile.get("avatar")
        disp = profile.get("display_name", username)
        av_html = f'<img src="{av}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid var(--q-accent);">' if av else f'<div style="width:80px;height:80px;border-radius:50%;background:var(--q-accent);color:white;display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:bold;">{disp[:1].upper()}</div>'
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:20px;margin-bottom:15px;">
            {av_html}
            <div>
                <h3 style="margin:0;">{disp}</h3>
                <p style="margin:0;color:var(--q-text-3);">@{username}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("This is a public profile. Private portfolio data is hidden.")
    else:
        st.error("User not found.")


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
            background: linear-gradient(145deg, rgba(28,32,45,.96), rgba(8,11,18,.98));
            border: 1px solid rgba(112,126,171,.28);
            border-radius: 14px;
            padding: 14px;
            min-height: 610px;
            box-shadow: 0 18px 45px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.04);
        }
        .chat-rail {
            background: linear-gradient(180deg, rgba(31,35,48,.95), rgba(11,14,22,.98));
            border-right: 1px solid rgba(112,126,171,.2);
            border-radius: 12px 0 0 12px;
            min-height: 580px;
            padding: 12px 10px;
        }
        .chat-title { color: var(--q-text); font-size: 1.25rem; font-weight: 600; margin: 4px 0 18px; }
        .chat-title-icon { color: #8b6cff; margin-right: 7px; }
        .chat-header { display:flex; align-items:center; gap:12px; border-bottom:1px solid rgba(112,126,171,.16); padding:2px 4px 16px; }
        .chat-avatar { width:54px; height:54px; border-radius:50%; display:grid; place-items:center; background:linear-gradient(145deg,#323b52,#111621); border:2px solid #697591; color:#aeb8ce; font-size:1.55rem; box-shadow:0 0 0 4px rgba(69,78,106,.18); }
        .chat-online { width:12px; height:12px; border-radius:50%; background:#26c281; border:2px solid #101520; margin-left:-23px; margin-top:38px; }
        .chat-header-name { color:var(--q-text); font-size:1.25rem; font-weight:600; }
        .chat-header-status { color:var(--q-text-3); font-size:.78rem; margin-top:2px; }
        .chat-header-status span { color:#26c281; }
        .chat-empty { min-height:470px; display:grid; place-items:center; color:var(--q-text-3); text-align:center; }
        .chat-rail .stButton > button { border-color:rgba(112,126,171,.22); background:rgba(25,29,42,.7); }
        .chat-rail .stButton > button:hover { border-color:#7e62ff; background:rgba(102,76,214,.15); }
        .chat-action { border:1px solid rgba(126,98,255,.6); border-radius:10px; padding:11px 12px; color:var(--q-text-2); background:rgba(18,20,30,.7); margin:10px 0; }
        .chat-action strong { color:var(--q-text); font-size:.86rem; }
        .chat-action small { display:block; color:var(--q-text-3); margin-top:2px; }
        @media (max-width: 760px) {
            .chat-shell { padding:8px; min-height:0; }
            .chat-rail { min-height:0; border-right:0; border-bottom:1px solid rgba(112,126,171,.2); border-radius:10px; }
            .chat-header-name { font-size:1.05rem; }
        }
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
                hdr0, hdr1, hdr2, hdr3 = st.columns([1, 4, 1, 1])
                with hdr0:
                    if st.button("←", key="chat_back", help="Back to conversations"):
                        st.session_state.active_chat_id = None
                        st.rerun(scope="fragment")
                with hdr1:
                    icon = "👤" if chat_info["type"] == "direct" else "👥"
                    if chat_info["type"] == "direct":
                        other = [p for p in chat_info["participants"] if p != _chat_user]
                        title = other[0] if other else "Chat"
                    else:
                        title = chat_info["name"]
                        members_str = ", ".join(chat_info["participants"])
                    _initial = title[:1].upper() if title else "?"
                    if chat_info["type"] == "direct" and other:
                        _is_online = firebase_db.is_user_online(other[0])
                    else:
                        _is_online = False
                    _presence_label = "Online" if _is_online else "Offline"
                    _presence_color = "#26c281" if _is_online else "var(--q-text-3)"
                    _presence_dot = "<div class='chat-online'></div>" if _is_online else ""
                    st.markdown(f"<div class='chat-header'><div class='chat-avatar'>{_initial}</div>{_presence_dot}<div><div class='chat-header-name'>{title}</div><div class='chat-header-status'>Status: <span style='color:{_presence_color}'>{_presence_label}</span></div></div></div>", unsafe_allow_html=True)
                    if chat_info["type"] == "group":
                        st.caption(f"Members: {members_str}")
                with hdr2:
                    if st.button("🔄", key="chat_refresh", help="Refresh messages"):
                        st.rerun(scope="fragment")
                with hdr3:
                    _header_action = "👤" if chat_info["type"] == "direct" else "ⓘ"
                    if st.button(_header_action, key="chat_details", help="Open profile or chat details"):
                        if chat_info["type"] == "direct":
                            other = [p for p in chat_info["participants"] if p != _chat_user]
                            if other:
                                _show_public_profile(other[0])
                        else:
                            st.info(f"Members: {', '.join(chat_info['participants'])}")

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

                st.markdown("<div style='height:1px;background:rgba(112,126,171,.14);margin:0 0 12px;'></div>", unsafe_allow_html=True)

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
                                    <div class="label" style="margin-top:6px;">Growth</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('growth_abs', 0):+,.0f}</div>
                                </div>"""
                            bubble += f'<div class="chat-time">{time_str}</div></div>'
                            msgs_html += f'<div class="chat-msg-row sent">{bubble}</div>'
                        else:
                            # ── Received message ─────────────────────────────
                            sender = msg["from"]
                            bubble = f'<div class="chat-bubble received"><div class="chat-sender"><a href="?page=Chat&view_profile={sender}" target="_self" style="text-decoration:none;color:inherit;">{sender}</a></div>{msg["text"]}'
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
                                    <div class="label" style="margin-top:6px;">Growth</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('growth_abs', 0):+,.0f}</div>
                                </div>"""
                            bubble += f'<div class="chat-time">{time_str}</div></div>'
                            msgs_html += f'<div class="chat-msg-row received">{bubble}</div>'

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
