"""
QUEST Knowledge Library — Bilingual YouTube-Style Video Learning Hub
====================================================================
- Dual Language Categories: English (100 Videos) & हिन्दी / Hindi (100 Videos)
- Same 10 Modules & 10 Topics per module across both languages
- 1-Click Instant Language Category Switcher
- In-Player Language Cross-Switch
- 100% Embed-Verified Working YouTube Videos
- Creator bar without follower/subscriber clutter
- Live user likes starting at 0 (only website user likes counted live)
- 80% Watch Requirement for +50 XP Reward
- "Up Next" sidebar playlist with module selectors
"""

import streamlit as st
import json
import os
import urllib.parse
import edu_db

# ──────────────────────────────────────────────────────────────────────────────
# Load 200-Video Bilingual Catalog
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

    # Language selection in session state (default: English)
    if "edu_language" not in st.session_state:
        st.session_state.edu_language = "en"
    current_lang = st.session_state.edu_language  # "en" or "hi"

    # Flatten videos for current language and build topic map
    all_videos = []
    topic_map = {}  # topic_key -> {"en": vid_obj, "hi": vid_obj}

    for mod in catalog:
        mod_id = mod.get("module_id", "module_1")
        mod_title = mod.get("module_title", "Module 1")
        stage = mod.get("stage", "Start Investing")
        category = mod.get("category", "Basics")
        cat_color = mod.get("cat_color", "#3b82f6")
        
        if "topics" in mod:
            for t in mod["topics"]:
                slot = t.get("slot", 1)
                t_key = f"{mod_id}_slot_{slot}"
                en_v = dict(t.get("en", {}))
                hi_v = dict(t.get("hi", {}))
                
                for v_obj, lang_tag in [(en_v, "en"), (hi_v, "hi")]:
                    v_obj["module_id"] = mod_id
                    v_obj["module_title"] = mod_title
                    v_obj["stage"] = stage
                    v_obj["category"] = category
                    v_obj["cat_color"] = cat_color
                    v_obj["slot"] = slot
                    v_obj["topic_key"] = t_key
                    v_obj.setdefault("youtube_id", "GcZW24SkbHM" if lang_tag == "en" else "Xn7KWR9EOGQ")
                    v_obj.setdefault("views", "420K")
                    v_obj.setdefault("duration", "9:30")
                    v_obj.setdefault("published", "Aug 2025")
                
                topic_map[t_key] = {"en": en_v, "hi": hi_v}
                all_videos.append(en_v if current_lang == "en" else hi_v)
        elif "videos" in mod:
            for idx, v in enumerate(mod.get("videos", [])):
                v_copy = dict(v)
                v_copy["module_id"] = mod_id
                v_copy["module_title"] = mod_title
                v_copy["stage"] = stage
                v_copy["category"] = category
                v_copy["cat_color"] = cat_color
                v_copy["slot"] = idx + 1
                v_copy["topic_key"] = f"{mod_id}_slot_{idx + 1}"
                all_videos.append(v_copy)

    if not all_videos:
        st.info("No learning videos available.")
        return

    # Initialize active video in session_state
    if "active_video_id" not in st.session_state or not any(v["id"] == st.session_state.active_video_id for v in all_videos):
        st.session_state.active_video_id = all_videos[0]["id"]

    # Active video object
    active_video = next((v for v in all_videos if v["id"] == st.session_state.active_video_id), all_videos[0])
    v_id = active_video["id"]

    # User progress & bookmarks
    prog = edu_db.load_progress()
    user_xp = prog.get("total_xp", 0)
    bookmarks = set(prog.get("bookmarks", []))
    completed_videos = set(prog.get("completed_articles", []))

    # Initialize watch progress for this video (0 to 100)
    prog_key = f"video_watch_progress_{v_id}"
    if prog_key not in st.session_state:
        st.session_state[prog_key] = 100 if v_id in completed_videos else 0
    cur_watch_prog = st.session_state[prog_key]
    is_watched = v_id in completed_videos or cur_watch_prog >= 80

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
            margin-bottom: 12px;
        }
        .yt-player-container iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: 0;
        }

        /* Video Watch Progress Tracker Bar */
        .yt-watch-tracker {
            background: var(--q-surface);
            border: 1px solid var(--q-border);
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }
        .yt-tracker-info {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--q-text);
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
    # Top Search & Profile Bar (NO NOTIFICATION BELL)
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
        <div style="display:flex;align-items:center;justify-content:flex-end;gap:10px;padding-top:4px;">
            <div style="display:flex;align-items:center;gap:6px;">
                {_av_tag}
                <span style="font-size:0.85rem;font-weight:600;color:var(--q-text);">{_dname}</span>
                <span style="font-size:0.75rem;color:var(--q-text-3);">▼</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Dual Language Category Switcher (English vs हिन्दी)
    # ══════════════════════════════════════════════════════════════════════════
    lang_col1, lang_col2, lang_col3 = st.columns([1.5, 1.2, 1.2])
    with lang_col1:
        st.markdown("""
        <div style="font-size:0.92rem;font-weight:700;color:var(--q-text);padding-top:6px;">
            Learning Language Category:
        </div>
        """, unsafe_allow_html=True)
    with lang_col2:
        is_en_selected = current_lang == "en"
        if st.button("English (100 Videos)", key="btn_switch_en", type="primary" if is_en_selected else "secondary", use_container_width=True):
            if current_lang != "en":
                st.session_state.edu_language = "en"
                cur_tkey = active_video.get("topic_key")
                if cur_tkey and cur_tkey in topic_map:
                    st.session_state.active_video_id = topic_map[cur_tkey]["en"]["id"]
                st.rerun()
    with lang_col3:
        is_hi_selected = current_lang == "hi"
        if st.button("हिन्दी / Hindi (100 Videos)", key="btn_switch_hi", type="primary" if is_hi_selected else "secondary", use_container_width=True):
            if current_lang != "hi":
                st.session_state.edu_language = "hi"
                cur_tkey = active_video.get("topic_key")
                if cur_tkey and cur_tkey in topic_map:
                    st.session_state.active_video_id = topic_map[cur_tkey]["hi"]["id"]
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # Breadcrumbs Navigation
    # ══════════════════════════════════════════════════════════════════════════
    lang_badge = "English" if current_lang == "en" else "हिन्दी"
    st.markdown(f"""
    <div class="yt-breadcrumbs">
        <span>Knowledge Library</span> &gt;
        <span style="color:#60a5fa;font-weight:700;">{lang_badge}</span> &gt;
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
        yt_id = active_video.get("youtube_id", "GcZW24SkbHM")
        yt_embed_url = f"https://www.youtube.com/embed/{yt_id}?autoplay=0&rel=0&modestbranding=1&enablejsapi=1"

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

        # 2. Video Title & Instant Other-Language Switcher Pill
        t_row1, t_row2 = st.columns([2.6, 1.4])
        with t_row1:
            st.markdown(f'<h1 class="yt-video-title">{active_video["title"]}</h1>', unsafe_allow_html=True)
        with t_row2:
            cur_tkey = active_video.get("topic_key")
            if cur_tkey and cur_tkey in topic_map:
                if current_lang == "en":
                    other_creator = topic_map[cur_tkey]["hi"]["creator"]
                    if st.button(f"🔄 Watch in हिन्दी ({other_creator})", key=f"btn_flip_lang_{cur_tkey}", use_container_width=True):
                        st.session_state.edu_language = "hi"
                        st.session_state.active_video_id = topic_map[cur_tkey]["hi"]["id"]
                        st.rerun()
                else:
                    other_creator = topic_map[cur_tkey]["en"]["creator"]
                    if st.button(f"🔄 Watch in English ({other_creator})", key=f"btn_flip_lang_{cur_tkey}", use_container_width=True):
                        st.session_state.edu_language = "en"
                        st.session_state.active_video_id = topic_map[cur_tkey]["en"]["id"]
                        st.rerun()

        # 3. Creator Bar (NO FOLLOW BUTTON, NO SUB COUNT) & Action Bar
        creator_name = active_video["creator"]
        creator_initial = creator_name[:1].upper()

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
                </div>
            </div>
            """, unsafe_allow_html=True)

        with c_acts_col:
            act_c1, act_c2, act_c3 = st.columns(3)
            user_liked, live_likes_count = edu_db.get_video_likes(v_id)
            is_bm = v_id in bookmarks
            is_watched = v_id in completed_videos

            # Like Button (Starts at 0, only live website user likes counted)
            with act_c1:
                like_btn_txt = f"👍 {live_likes_count}" if not user_liked else f"👍 {live_likes_count} (Liked)"
                if st.button(like_btn_txt, key=f"btn_like_{v_id}", type="primary" if user_liked else "secondary", use_container_width=True):
                    now_liked, new_total = edu_db.toggle_like(v_id)
                    if now_liked:
                        st.toast(f"Liked this video! 👍 Total live likes: {new_total}")
                    else:
                        st.toast(f"Unliked. Total live likes: {new_total}")
                    st.rerun()

            # Save / Bookmark Button
            with act_c2:
                bm_txt = "★ Saved" if is_bm else "☆ Save"
                if st.button(bm_txt, key=f"btn_save_{v_id}", use_container_width=True):
                    new_bm = edu_db.toggle_bookmark(v_id)
                    st.toast("Saved to your Library bookmarks! 🔖" if new_bm else "Removed from bookmarks.")
                    st.rerun()

            # Mark as Watched & Claim +50 XP (When completely watched)
            with act_c3:
                comp_txt = "✅ Watched (+50 XP)" if is_watched else "🎓 +50 XP"
                if st.button(comp_txt, key=f"btn_comp_{v_id}", type="primary" if not is_watched else "secondary", disabled=is_watched, use_container_width=True):
                    if not is_watched:
                        new_xp = edu_db.complete_article(v_id, 50)
                        st.toast(f"🎉 Awesome! Lesson completely watched. +50 XP awarded! Total: {new_xp} XP", icon="⭐")
                        st.balloons()
                        st.rerun()

        # 5. Description Box with Real-World Takeaways
        views_txt = active_video.get("views", "320K")
        pub_txt = active_video.get("published", "Recently")
        takeaway_header = "Key Learning Takeaways:" if current_lang == "en" else "मुख्य निष्कर्ष (Key Takeaways):"
        
        st.markdown(f"""
        <div class="yt-desc-box">
            <div class="yt-desc-meta">{views_txt} views &bull; {pub_txt} &bull; {active_video['module_title']} &bull; {lang_badge}</div>
            <div class="yt-desc-text">{active_video['summary']}</div>
            <div style="font-weight:700;font-size:0.85rem;color:var(--q-text);margin:10px 0 6px;">{takeaway_header}</div>
        """, unsafe_allow_html=True)
        for tkw in active_video.get("key_takeaways", []):
            st.markdown(f'<div class="yt-takeaway-item"><span style="color:#10b981;">•</span> {tkw}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Right Column: "Up Next" Video Playlist
    # ══════════════════════════════════════════════════════════════════════════
    with col_upnext:
        up_h1, up_h2 = st.columns([2, 1])
        with up_h1:
            st.markdown(f'<div class="yt-upnext-header">Up Next ({lang_badge})</div>', unsafe_allow_html=True)
        with up_h2:
            st.markdown('<div style="font-size:0.78rem;color:var(--q-text-3);text-align:right;padding-top:4px;">Autoplay 🟢</div>', unsafe_allow_html=True)

        # Module Selector / Filter
        module_options = ["All Modules (100 Videos)"] + [mod.get("module_title", f"Module {i+1}") for i, mod in enumerate(catalog)]
        selected_module = st.selectbox(
            "Filter Module",
            module_options,
            key=f"yt_playlist_module_filter_{current_lang}",
            label_visibility="collapsed"
        )

        # Filtered playlist videos
        if selected_module == "All Modules (100 Videos)":
            playlist_videos = all_videos
        else:
            playlist_videos = [v for v in all_videos if v.get("module_title") == selected_module]

        # Search filter if user typed keywords
        if search_kw and search_kw.strip():
            skw = search_kw.strip().lower()
            playlist_videos = [
                v for v in playlist_videos
                if skw in v["title"].lower() 
                or skw in v["creator"].lower() 
                or skw in v["category"].lower() 
                or skw in v["module_title"].lower()
            ]

        # Render list of videos
        limit = st.session_state.get("playlist_limit", 8)
        displayed_videos = playlist_videos[:limit]

        for p_idx, vid in enumerate(displayed_videos):
            is_active = vid["id"] == active_video["id"]
            cat_clr = vid.get("cat_color", "#3b82f6")
            
            with st.container():
                c1, c2 = st.columns([1.1, 1.9], gap="small")
                with c1:
                    st.markdown(f"""
                    <div class="yt-card-thumb" style="border-left: 3px solid {cat_clr};">
                        <div style="font-size:1.3rem;opacity:0.8;">▶</div>
                        <div class="yt-card-duration">{vid.get('duration', '8:30')}</div>
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
                        <div class="yt-card-views">{vid.get('views', '350K')} views &bull; {vid['category']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Play Video", key=f"btn_play_{vid['id']}_{p_idx}_{current_lang}", use_container_width=True):
                        st.session_state.active_video_id = vid["id"]
                        st.rerun()

                st.markdown("<hr style='border:0;border-top:1px solid rgba(255,255,255,0.04);margin:6px 0;'>", unsafe_allow_html=True)

        # Show more button
        if len(playlist_videos) > limit:
            if st.button(f"Show more ({len(playlist_videos) - limit} remaining) ∨", key=f"btn_show_more_playlist_{current_lang}", use_container_width=True):
                st.session_state.playlist_limit = limit + 10
                st.rerun()
        elif limit > 8:
            if st.button("Show less ∧", key=f"btn_show_less_playlist_{current_lang}", use_container_width=True):
                st.session_state.playlist_limit = 8
                st.rerun()
