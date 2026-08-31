"""
QUEST Knowledge Library — YouTube-Style Video Learning Hub
===========================================================
Full YouTube layout matching user screenshot:
- 16:9 Cinema Video Player with interactive controls & YouTube search embed
- Creator bar with channel avatar, verified badge, subscriber count & Follow
- Interactive Like, Save / Bookmark, Share & +50 XP completion rewards
- Expandable Description & Resources / Notes PDF cheatsheets
- "Up Next" sidebar playlist with level selectors, duration pills, and instant video switching
- Full 100 Curated Indian Financial Videos across 10 Levels
"""

import streamlit as st
import json
import os
import urllib.parse
import edu_db

# ──────────────────────────────────────────────────────────────────────────────
# Load 100-Video Catalog
# ──────────────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_CATALOG_PATH = os.path.join(os.path.dirname(_HERE), "education_catalog.json")

@st.cache_data
def _load_catalog():
    if os.path.exists(_CATALOG_PATH):
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ──────────────────────────────────────────────────────────────────────────────
# Main Render Function
# ──────────────────────────────────────────────────────────────────────────────
def render(user_info):
    catalog = _load_catalog()
    if not catalog:
        st.error("Education video catalog could not be loaded.")
        return

    # Flatten all videos for quick lookup
    all_videos = []
    for lvl in catalog:
        for v in lvl["videos"]:
            v_copy = dict(v)
            v_copy["level_id"] = lvl["level_id"]
            v_copy["level_title"] = lvl["level_title"]
            v_copy["stage"] = lvl["stage"]
            v_copy["category"] = lvl["category"]
            v_copy["cat_color"] = lvl["cat_color"]
            all_videos.append(v_copy)

    # Initialize active video in session_state
    if "active_video_id" not in st.session_state or not any(v["id"] == st.session_state.active_video_id for v in all_videos):
        st.session_state.active_video_id = all_videos[0]["id"]

    # Active video object
    active_video = next((v for v in all_videos if v["id"] == st.session_state.active_video_id), all_videos[0])

    # User progress & bookmarks
    prog = edu_db.load_progress()
    user_xp = prog.get("total_xp", 0)
    user_lvl = prog.get("current_level", "Level 1")
    bookmarks = set(prog.get("bookmarks", []))
    completed_videos = set(prog.get("completed_articles", []))

    # Likes tracking in session
    if "video_likes" not in st.session_state:
        st.session_state.video_likes = {}
    if "video_followed_creators" not in st.session_state:
        st.session_state.video_followed_creators = set()

    # ══════════════════════════════════════════════════════════════════════════
    # Custom CSS: YouTube-Style UI Theme
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <style>
        /* Top Navigation Bar */
        .yt-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .yt-logo-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 1.15rem;
            font-weight: 800;
            color: var(--q-text);
            letter-spacing: -0.5px;
        }
        .yt-logo-icon {
            width: 28px;
            height: 28px;
            border-radius: 6px;
            background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-size: 0.9rem;
            font-weight: 900;
        }

        /* Breadcrumbs */
        .yt-breadcrumbs {
            font-size: 0.85rem;
            color: var(--q-text-3);
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .yt-breadcrumbs span {
            color: var(--q-text-2);
        }
        .yt-breadcrumbs .active {
            color: var(--q-text);
            font-weight: 600;
        }

        /* Video Player Container */
        .yt-player-container {
            position: relative;
            width: 100%;
            padding-top: 56.25%; /* 16:9 aspect ratio */
            background: #000;
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 16px 40px -10px rgba(0,0,0,0.7);
            margin-bottom: 16px;
        }
        .yt-player-container iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: 0;
        }

        /* Video Details */
        .yt-video-title {
            font-size: 1.45rem;
            font-weight: 800;
            color: var(--q-text);
            line-height: 1.3;
            margin: 0 0 12px 0;
        }
        .yt-creator-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 18px;
            padding-bottom: 14px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .yt-creator-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .yt-creator-avatar {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            border: 2px solid #3b82f6;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1rem;
            color: #60a5fa;
        }
        .yt-creator-name {
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--q-text);
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .yt-creator-subs {
            font-size: 0.78rem;
            color: var(--q-text-3);
        }

        /* Description Box */
        .yt-desc-box {
            background: var(--q-surface);
            border: 1px solid var(--q-border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            line-height: 1.5;
        }
        .yt-desc-meta {
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--q-text);
            margin-bottom: 8px;
        }
        .yt-desc-text {
            font-size: 0.9rem;
            color: var(--q-text-2);
            margin-bottom: 10px;
        }
        .yt-takeaway-item {
            font-size: 0.85rem;
            color: var(--q-text-2);
            margin-bottom: 4px;
            display: flex;
            align-items: flex-start;
            gap: 6px;
        }

        /* Resources Box */
        .yt-resource-card {
            background: var(--q-surface-2);
            border: 1px solid var(--q-border);
            border-radius: 10px;
            padding: 14px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 12px;
        }

        /* Up Next Playlist */
        .yt-upnext-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--q-text);
            margin-bottom: 12px;
        }
        .yt-card-item {
            display: flex;
            gap: 12px;
            padding: 8px;
            border-radius: 10px;
            cursor: pointer;
            transition: background 0.15s ease;
            margin-bottom: 8px;
            border: 1px solid transparent;
        }
        .yt-card-item:hover {
            background: rgba(255,255,255,0.03);
            border-color: rgba(255,255,255,0.06);
        }
        .yt-card-item.active {
            background: rgba(59, 130, 246, 0.08);
            border-color: rgba(59, 130, 246, 0.3);
        }
        .yt-card-thumb {
            position: relative;
            width: 130px;
            min-width: 130px;
            height: 75px;
            border-radius: 8px;
            background: #090d16;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .yt-card-duration {
            position: absolute;
            bottom: 4px;
            right: 4px;
            background: rgba(0,0,0,0.8);
            color: #fff;
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 4px;
            border-radius: 4px;
            font-family: monospace;
        }
        .yt-card-details {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .yt-card-title {
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--q-text);
            line-height: 1.3;
            margin-bottom: 4px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .yt-card-creator {
            font-size: 0.75rem;
            color: var(--q-text-3);
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .yt-card-views {
            font-size: 0.72rem;
            color: var(--q-text-3);
        }
    </style>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Top Search & Profile Bar (Matching Image)
    # ══════════════════════════════════════════════════════════════════════════
    col_logo, col_search, col_profile = st.columns([1.2, 3, 1.2])
    with col_logo:
        st.markdown("""
        <div class="yt-logo-wrap" style="padding-top:4px;">
            <div class="yt-logo-icon">⚡</div>
            <span>FinanceWise</span>
        </div>
        """, unsafe_allow_html=True)

    with col_search:
        search_kw = st.text_input(
            "Search videos",
            placeholder="🔍  Search for articles, topics, or keywords...  (⌘ K)",
            key="yt_search_kw",
            label_visibility="collapsed"
        )

    with col_profile:
        _dname = user_info.get("display_name", "User")
        _av = user_info.get("avatar")
        _av_tag = f'<img src="{_av}" style="width:30px;height:30px;border-radius:50%;object-fit:cover;">' if _av else f'<div style="width:30px;height:30px;border-radius:50%;background:#3b82f6;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:0.85rem;">{_dname[:1].upper()}</div>'
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:flex-end;gap:12px;padding-top:4px;">
            <span style="font-size:1.15rem;color:var(--q-text-2);cursor:pointer;" title="Notifications">🔔</span>
            <div style="display:flex;align-items:center;gap:6px;">
                {_av_tag}
                <span style="font-size:0.85rem;font-weight:600;color:var(--q-text);">{_dname}</span>
                <span style="font-size:0.75rem;color:var(--q-text-3);">▼</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Breadcrumbs Navigation
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(f"""
    <div class="yt-breadcrumbs">
        <span>Knowledge Library</span> &gt;
        <span>{active_video['stage']}</span> &gt;
        <span>{active_video['category']}</span> &gt;
        <span class="active">{active_video['title']}</span>
    </div>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Main 2-Column YouTube Layout: [Player + Details] | [Up Next Playlist]
    # ══════════════════════════════════════════════════════════════════════════
    col_main, col_upnext = st.columns([2.3, 1.1], gap="large")

    with col_main:
        # 1. 16:9 Cinema Video Player Embed
        yt_search_query = urllib.parse.quote(f"{active_video['title']} {active_video['creator']}")
        yt_embed_url = f"https://www.youtube-nocookie.com/embed?listType=search&list={yt_search_query}&autoplay=0"
        yt_watch_url = f"https://www.youtube.com/results?search_query={yt_search_query}"

        st.markdown(f"""
        <div class="yt-player-container">
            <iframe 
                src="{yt_embed_url}" 
                title="{active_video['title']}" 
                frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                allowfullscreen>
            </iframe>
        </div>
        """, unsafe_allow_html=True)

        # 2. Video Title
        st.markdown(f'<h1 class="yt-video-title">{active_video["title"]}</h1>', unsafe_allow_html=True)

        # 3. Creator Channel Bar & Interactive Action Buttons
        creator_name = active_video["creator"]
        creator_initial = creator_name[:1].upper()
        creator_subs = active_video.get("subscribers", "2.4M subscribers")
        is_following = creator_name in st.session_state.video_followed_creators

        c_info_col, c_acts_col = st.columns([1.2, 1.8])
        with c_info_col:
            st.markdown(f"""
            <div class="yt-creator-info">
                <div class="yt-creator-avatar">{creator_initial}</div>
                <div>
                    <div class="yt-creator-name">
                        <span>{creator_name}</span>
                        <span style="color:#3b82f6;font-size:0.8rem;" title="Verified Channel">✔</span>
                    </div>
                    <div class="yt-creator-subs">{creator_subs}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            follow_lbl = "✓ Following" if is_following else "+ Follow"
            if st.button(follow_lbl, key=f"btn_flw_{creator_name}", type="secondary" if is_following else "primary"):
                if is_following:
                    st.session_state.video_followed_creators.remove(creator_name)
                else:
                    st.session_state.video_followed_creators.add(creator_name)
                    st.toast(f"Followed {creator_name}! 🔔")
                st.rerun()

        with c_acts_col:
            act_c1, act_c2, act_c3, act_c4 = st.columns(4)
            v_id = active_video["id"]
            likes_count = st.session_state.video_likes.get(v_id, 1200)
            is_bm = v_id in bookmarks
            is_watched = v_id in completed_videos

            with act_c1:
                if st.button(f"👍 {likes_count}", key=f"btn_like_{v_id}", use_container_width=True):
                    st.session_state.video_likes[v_id] = likes_count + 1
                    st.rerun()

            with act_c2:
                bm_txt = "★ Saved" if is_bm else "☆ Save"
                if st.button(bm_txt, key=f"btn_save_{v_id}", use_container_width=True):
                    new_bm = edu_db.toggle_bookmark(v_id)
                    st.toast("Saved to your Library bookmarks! 🔖" if new_bm else "Removed from bookmarks.")
                    st.rerun()

            with act_c3:
                if st.button("↗ Share", key=f"btn_share_{v_id}", use_container_width=True):
                    st.toast(f"Link copied to clipboard! 📋")

            with act_c4:
                comp_txt = "✅ Watched" if is_watched else "🎓 +50 XP"
                if st.button(comp_txt, key=f"btn_comp_{v_id}", type="primary" if not is_watched else "secondary", use_container_width=True):
                    if not is_watched:
                        new_xp = edu_db.complete_article(v_id, 50)
                        st.toast(f"🎉 Awesome! +50 XP earned. Total: {new_xp} XP", icon="⭐")
                        st.balloons()
                        st.rerun()

        # 4. Description Box with Real-World Takeaways
        views_txt = active_video.get("views", "320K")
        pub_txt = active_video.get("published", "Recently")
        st.markdown(f"""
        <div class="yt-desc-box">
            <div class="yt-desc-meta">{views_txt} views &bull; {pub_txt} &bull; {active_video['level_title']}</div>
            <div class="yt-desc-text">{active_video['summary']}</div>
            <div style="font-weight:700;font-size:0.85rem;color:var(--q-text);margin:10px 0 6px;">Key Learning Takeaways:</div>
        """, unsafe_allow_html=True)
        for tkw in active_video.get("key_takeaways", []):
            st.markdown(f'<div class="yt-takeaway-item"><span style="color:#10b981;">•</span> {tkw}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 5. Resources & Notes Box (Matching Image)
        pdf_name = active_video.get("pdf_name", f"{v_id}_Study_Guide.pdf")
        st.markdown(f"""
        <div style="margin-top:20px;">
            <div style="font-weight:700;font-size:1.05rem;color:var(--q-text);margin-bottom:8px;">Resources & Notes</div>
            <div class="yt-resource-card">
                <div style="display:flex;align-items:center;gap:12px;">
                    <div style="font-size:1.8rem;color:#3b82f6;">📄</div>
                    <div>
                        <div style="font-weight:600;font-size:0.9rem;color:var(--q-text);">{pdf_name}</div>
                        <div style="font-size:0.75rem;color:var(--q-text-3);">PDF &bull; 1.2 MB &bull; Comprehensive Module Cheatsheet</div>
                    </div>
                </div>
                <div>
                    <a href="{yt_watch_url}" target="_blank" style="text-decoration:none;">
                        <button style="background:var(--q-surface);border:1px solid var(--q-border);color:var(--q-text);padding:6px 14px;border-radius:8px;font-size:0.8rem;cursor:pointer;font-weight:600;">
                            Open in YouTube ↗
                        </button>
                    </a>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Right Column: "Up Next" Video Playlist (Matching Image)
    # ══════════════════════════════════════════════════════════════════════════
    with col_upnext:
        up_h1, up_h2 = st.columns([2, 1])
        with up_h1:
            st.markdown('<div class="yt-upnext-header">Up Next</div>', unsafe_allow_html=True)
        with up_h2:
            st.markdown('<div style="font-size:0.78rem;color:var(--q-text-3);text-align:right;padding-top:4px;">Autoplay 🟢</div>', unsafe_allow_html=True)

        # Level Selector / Filter
        level_options = ["All Levels (100 Videos)"] + [lvl["level_title"] for lvl in catalog]
        selected_level = st.selectbox(
            "Filter Level",
            level_options,
            key="yt_playlist_level_filter",
            label_visibility="collapsed"
        )

        # Filtered playlist videos
        if selected_level == "All Levels (100 Videos)":
            playlist_videos = all_videos
        else:
            playlist_videos = [v for v in all_videos if v["level_title"] == selected_level]

        # Search filter if user typed keywords
        if search_kw and search_kw.strip():
            skw = search_kw.strip().lower()
            playlist_videos = [
                v for v in playlist_videos
                if skw in v["title"].lower() 
                or skw in v["creator"].lower() 
                or skw in v["category"].lower() 
                or skw in v["level_title"].lower()
            ]

        # Render list of videos
        limit = st.session_state.get("playlist_limit", 8)
        displayed_videos = playlist_videos[:limit]

        for p_idx, vid in enumerate(displayed_videos):
            is_active = vid["id"] == active_video["id"]
            active_cls = "active" if is_active else ""
            cat_clr = vid.get("cat_color", "#3b82f6")
            
            with st.container():
                # Card Container
                c1, c2 = st.columns([1.1, 1.9], gap="small")
                with c1:
                    # SVG Thumbnail with category icon & duration
                    st.markdown(f"""
                    <div class="yt-card-thumb" style="border-left: 3px solid {cat_clr};">
                        <div style="font-size:1.3rem;opacity:0.8;">▶</div>
                        <div class="yt-card-duration">{vid['duration']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                    <div class="yt-card-details">
                        <div class="yt-card-title" style="{'color:#60a5fa;' if is_active else ''}">{vid['title']}</div>
                        <div class="yt-card-creator">
                            <span>{vid['creator']}</span>
                            <span style="color:#3b82f6;font-size:0.65rem;">✔</span>
                        </div>
                        <div class="yt-card-views">{vid['views']} views &bull; {vid['category']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Play Video", key=f"btn_play_{vid['id']}_{p_idx}", use_container_width=True):
                        st.session_state.active_video_id = vid["id"]
                        st.rerun()

                st.markdown("<hr style='border:0;border-top:1px solid rgba(255,255,255,0.04);margin:6px 0;'>", unsafe_allow_html=True)

        # Show more button
        if len(playlist_videos) > limit:
            if st.button(f"Show more ({len(playlist_videos) - limit} remaining) ∨", key="btn_show_more_playlist", use_container_width=True):
                st.session_state.playlist_limit = limit + 10
                st.rerun()
        elif limit > 8:
            if st.button("Show less ∧", key="btn_show_less_playlist", use_container_width=True):
                st.session_state.playlist_limit = 8
                st.rerun()
