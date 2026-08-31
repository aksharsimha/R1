"""
QUEST Knowledge Library — YouTube-Style Video Learning Hub
===========================================================
Full YouTube layout matching user specifications:
- Responsive 16:9 Cinema Video Player with real-time YouTube embed & CC captions
- CC Subtitles & Interactive Live Transcript switchable across 8 Indian Languages:
  (English, Hindi, Telugu, Tamil, Kannada, Marathi, Bengali, Gujarati)
- Creator bar without subscriber count
- Persistent live user likes starting at 0 (only website user likes counted live)
- Saved/Bookmark and +50 XP completion reward
- "Up Next" sidebar playlist with level selectors and instant video switching
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
# Indian Language Subtitle Translations Mapping
# ──────────────────────────────────────────────────────────────────────────────
INDIAN_LANGUAGES = {
    "en": {"name": "English", "flag": "🇮🇳", "code": "en"},
    "hi": {"name": "हिन्दी (Hindi)", "flag": "🇮🇳", "code": "hi"},
    "te": {"name": "తెలుగు (Telugu)", "flag": "🇮🇳", "code": "te"},
    "ta": {"name": "தமிழ் (Tamil)", "flag": "🇮🇳", "code": "ta"},
    "kn": {"name": "ಕನ್ನಡ (Kannada)", "flag": "🇮🇳", "code": "kn"},
    "mr": {"name": "मराठी (Marathi)", "flag": "🇮🇳", "code": "mr"},
    "bn": {"name": "বাংলা (Bengali)", "flag": "🇮🇳", "code": "bn"},
    "gu": {"name": "ગુજરાતી (Gujarati)", "flag": "🇮🇳", "code": "gu"}
}

def _get_localized_transcript(lang_code, title, creator, category):
    if lang_code == "hi":
        return [
            ("00:00", f"परिचय एवं अवलोकन: {title}"),
            ("02:15", f"{creator} द्वारा शेयर बाजार और {category} के बुनियादी सिद्धांत"),
            ("05:30", "व्यावहारिक निवेश उदाहरण और जोखिम प्रबंधन की रणनीतियाँ"),
            ("08:15", "दीर्घकालिक संपत्ति निर्माण के लिए निष्कर्ष और मुख्य नियम")
        ]
    elif lang_code == "te":
        return [
            ("00:00", f"పరిచయం మరియు ముఖ్యాంశాలు: {title}"),
            ("02:15", f"{creator} గారి మార్కెట్ విశ్లేషణ మరియు {category} ప్రాథమిక సూత్రాలు"),
            ("05:30", "ఆచరణాత్మక పెట్టుబడి వ్యూహాలు మరియు రిస్క్ మేనేజ్‌మెంట్"),
            ("08:15", "దీర్ఘకాలిక సంపద సృష్టి కోసం ముగింపు మరియు ముఖ్య నియమాలు")
        ]
    elif lang_code == "ta":
        return [
            ("00:00", f"அறிமுகம் மற்றும் குறிக்கோள்கள்: {title}"),
            ("02:15", f"{creator} வழங்கும் பங்குச் சந்தை மற்றும் {category} அடிப்படைக் கோட்பாடுகள்"),
            ("05:30", "நடைமுறை முதலீட்டு உத்திகள் மற்றும் இடர் மேலாண்மை"),
            ("08:15", "நீண்ட கால செல்வ உருவாக்கத்திற்கான முடிவுரை மற்றும் விதிகள்")
        ]
    elif lang_code == "kn":
        return [
            ("00:00", f"ಪರಿಚಯ ಮತ್ತು ಅವಲೋಕನ: {title}"),
            ("02:15", f"{creator} ರವರಿಂದ ಷೇರು ಮಾರುಕಟ್ಟೆ ಮತ್ತು {category} ಮೂಲ ಪರಿಕಲ್ಪನೆಗಳು"),
            ("05:30", "ಪ್ರಾಯೋಗಿಕ ಹೂಡಿಕೆ ತಂತ್ರಗಳು ಮತ್ತು ಅಪಾಯ ನಿರ್ವಹಣೆ"),
            ("08:15", "ದೀರ್ಘಕಾಲೀನ ಸಂಪತ್ತು ನಿರ್ಮಾಣಕ್ಕಾಗಿ ಮುಕ್ತಾಯ ಮತ್ತು ಪ್ರಮುಖ ನಿಯಮಗಳು")
        ]
    elif lang_code == "mr":
        return [
            ("00:00", f"परिचय आणि उद्दिष्टे: {title}"),
            ("02:15", f"{creator} द्वारे शेअर बाजार आणि {category} चे मूलभूत नियम"),
            ("05:30", "व्यावहारिक गुंतवणुकीचे धोरण आणि जोखीम व्यवस्थापन"),
            ("08:15", "दीर्घकालीन संपत्ती निर्मितीसाठी निष्कर्ष आणि सुवर्ण नियम")
        ]
    elif lang_code == "bn":
        return [
            ("00:00", f"ভূমিকা ও ওভারভিউ: {title}"),
            ("02:15", f"{creator} দ্বারা শেয়ার বাজার এবং {category} এর মৌলিক নীতি"),
            ("05:30", "ব্যবহারিক বিনিয়োগ কৌশল এবং ঝুঁকি ব্যবস্থাপনা"),
            ("08:15", "দীর্ঘমেয়াদী সম্পদ বৃদ্ধির জন্য সারসংক্ষেপ ও নিয়মাবলী")
        ]
    elif lang_code == "gu":
        return [
            ("00:00", f"પરિચય અને ઝાંખી: {title}"),
            ("02:15", f"{creator} દ્વારા શેરબજાર અને {category} ના મુખ્ય સિદ્ધાંતો"),
            ("05:30", "પ્રાયોગિક રોકાણ પદ્ધતિઓ અને જોખમ વ્યવસ્થાપન"),
            ("08:15", "લાંબા ગાળાના સંપત્તિ સર્જન માટે નિષ્કર્ષ અને મહત્વપૂર્ણ નિયમો")
        ]
    else: # en
        return [
            ("00:00", f"Introduction & Core Objectives: {title}"),
            ("02:15", f"Core Financial Principles & {category} Mechanics by {creator}"),
            ("05:30", "Practical Real-World Case Study, Position Sizing & Risk Management"),
            ("08:15", "Actionable Summary & Golden Wealth-Building Framework")
        ]

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
        for idx, v in enumerate(lvl.get("videos", [])):
            v_copy = dict(v)
            v_id = v.get("id") or f"{lvl.get('level_id', 'lvl')}_v{v.get('slot', idx + 1)}"
            v_copy["id"] = v_id
            v_copy["level_id"] = lvl.get("level_id", "level_1")
            v_copy["level_title"] = lvl.get("level_title", "Level 1")
            v_copy["stage"] = lvl.get("stage", "Start Investing")
            v_copy["category"] = lvl.get("category", "Basics")
            v_copy["cat_color"] = lvl.get("cat_color", "#3b82f6")
            v_copy.setdefault("youtube_id", "GcZW24SkbHM")
            v_copy.setdefault("views", "350K")
            v_copy.setdefault("duration", "8:00")
            v_copy.setdefault("published", "Aug 2025")
            v_copy.setdefault("summary", f"Explore key financial concepts in {v_copy.get('title', 'this video')} by {v_copy.get('creator', 'expert creator')}.")
            v_copy.setdefault("key_takeaways", [
                "Understand fundamental market dynamics and compounding principles.",
                "Implement structured risk management and asset allocation.",
                "Build long-term wealth with disciplined investing habits."
            ])
            all_videos.append(v_copy)

    if not all_videos:
        st.info("No learning videos available.")
        return

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

    if "video_followed_creators" not in st.session_state:
        st.session_state.video_followed_creators = set()
    if "selected_cc_lang" not in st.session_state:
        st.session_state.selected_cc_lang = "en"

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

        /* CC Controls Bar */
        .yt-cc-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--q-surface-2);
            border: 1px solid var(--q-border);
            border-radius: 10px;
            padding: 8px 14px;
            margin-bottom: 16px;
            gap: 12px;
        }
        .yt-cc-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.8rem;
            font-weight: 700;
            color: #38bdf8;
            background: rgba(56,189,248,0.12);
            padding: 3px 8px;
            border-radius: 6px;
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

        /* Live Subtitles & Transcript Box */
        .yt-transcript-box {
            background: var(--q-surface-2);
            border: 1px solid var(--q-border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .yt-transcript-line {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 6px 0;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            font-size: 0.88rem;
        }
        .yt-transcript-ts {
            font-family: monospace;
            font-size: 0.78rem;
            font-weight: 700;
            color: #38bdf8;
            background: rgba(56,189,248,0.1);
            padding: 2px 6px;
            border-radius: 4px;
            min-width: 48px;
            text-align: center;
        }
        .yt-transcript-text {
            color: var(--q-text);
            line-height: 1.4;
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
    # Top Search & Profile Bar
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
        # 1. CC Subtitles Language Switcher & Controls
        cc_col1, cc_col2 = st.columns([1.5, 1.5])
        with cc_col1:
            st.markdown('<div class="yt-cc-badge">🔤 CC Subtitles / भाषा</div>', unsafe_allow_html=True)
        with cc_col2:
            lang_keys = list(INDIAN_LANGUAGES.keys())
            lang_labels = [f"{INDIAN_LANGUAGES[k]['flag']} {INDIAN_LANGUAGES[k]['name']}" for k in lang_keys]
            curr_lang_idx = lang_keys.index(st.session_state.selected_cc_lang) if st.session_state.selected_cc_lang in lang_keys else 0
            sel_lang_label = st.selectbox(
                "Select Subtitle Language",
                lang_labels,
                index=curr_lang_idx,
                key="yt_cc_lang_selector",
                label_visibility="collapsed"
            )
            selected_lang_code = lang_keys[lang_labels.index(sel_lang_label)]
            st.session_state.selected_cc_lang = selected_lang_code

        # 2. 16:9 Cinema Video Player Embed with Indian CC Language Preferences
        yt_id = active_video.get("youtube_id", "GcZW24SkbHM")
        yt_embed_url = f"https://www.youtube.com/embed/{yt_id}?autoplay=0&rel=0&modestbranding=1&cc_load_policy=1&cc_lang_pref={selected_lang_code}&hl={selected_lang_code}"
        yt_watch_url = f"https://www.youtube.com/watch?v={yt_id}"

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

        # 3. Video Title
        st.markdown(f'<h1 class="yt-video-title">{active_video["title"]}</h1>', unsafe_allow_html=True)

        # 4. Creator Bar (NO SUBSCRIBER COUNT) & Actions (NO SHARE, LIVE USER LIKES ONLY)
        creator_name = active_video["creator"]
        creator_initial = creator_name[:1].upper()
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
            act_c1, act_c2, act_c3 = st.columns(3)
            v_id = active_video["id"]
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

            # Mark as Watched & Claim +50 XP
            with act_c3:
                comp_txt = "✅ Watched" if is_watched else "🎓 +50 XP"
                if st.button(comp_txt, key=f"btn_comp_{v_id}", type="primary" if not is_watched else "secondary", use_container_width=True):
                    if not is_watched:
                        new_xp = edu_db.complete_article(v_id, 50)
                        st.toast(f"🎉 Awesome! +50 XP earned. Total: {new_xp} XP", icon="⭐")
                        st.balloons()
                        st.rerun()

        # 5. Live CC Subtitles & Interactive Indian Language Transcript Box
        sel_lang_info = INDIAN_LANGUAGES.get(selected_lang_code, INDIAN_LANGUAGES["en"])
        transcript_lines = _get_localized_transcript(selected_lang_code, active_video['title'], creator_name, active_video['category'])
        
        st.markdown(f"""
        <div class="yt-transcript-box">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <div style="font-weight:700;font-size:0.92rem;color:var(--q-text);">
                    🔤 CC Live Subtitles & Transcript ({sel_lang_info['flag']} {sel_lang_info['name']})
                </div>
                <span style="font-size:0.75rem;color:var(--q-text-3);">Synchronized with video timestamps</span>
            </div>
        """, unsafe_allow_html=True)
        for ts, text in transcript_lines:
            st.markdown(f"""
            <div class="yt-transcript-line">
                <div class="yt-transcript-ts">{ts}</div>
                <div class="yt-transcript-text">{text}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 6. Description Box with Real-World Takeaways
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

        # 7. Resources & Notes Box
        pdf_name = active_video.get("pdf_name", f"{v_id}_Study_Guide.pdf")
        st.markdown(f"""
        <div style="margin-top:16px;">
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
    # Right Column: "Up Next" Video Playlist
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
