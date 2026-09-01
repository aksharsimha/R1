"""
QUEST Knowledge Library — Bilingual YouTube-Style Video Learning Hub with MICHAEL AI Assistant
=============================================================================================
- Dual Language Categories: English (100 Videos) & हिन्दी / Hindi (100 Videos)
- Same 10 Modules & 10 Topics per module across both languages
- 1-Click Instant Language Category Switcher
- In-Player Language Cross-Switch
- 100% Embed-Verified Working YouTube Videos
- Direct +50 XP Reward upon complete watch
- Creator bar without follower/subscriber clutter
- Live user likes starting at 0 (only website user likes counted live)
- "Up Next" sidebar playlist with module selectors
- ⚡ MICHAEL AI Video Study Assistant & Doubt Solver embedded right below the video player
"""

import streamlit as st
import json
import os
import urllib.parse
import urllib.request
import datetime
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
# MICHAEL AI Assistant Engine for Video Learning & Doubts
# ──────────────────────────────────────────────────────────────────────────────
def _get_michael_api_key():
    try:
        shared = (str(st.secrets.get("GROQ_API_KEY", "")).strip()
                  or str(st.secrets.get("GEMINI_API_KEY", "")).strip())
        if shared:
            return shared, ("groq" if shared.startswith("gsk_") else "gemini")
    except Exception:
        pass
    user_k = st.session_state.get("michael_api_key", "").strip()
    if user_k:
        return user_k, ("groq" if user_k.startswith("gsk_") else "gemini")
    return "", ""

def _ask_michael_video_ai(query, active_video, history):
    api_key, provider = _get_michael_api_key()
    v_title = active_video.get("title", "Investing Basics")
    v_creator = active_video.get("creator", "Finance Expert")
    v_module = active_video.get("module_title", "Module 1")
    v_lang = "Hindi" if active_video.get("language") == "hi" else "English"
    v_summary = active_video.get("summary", "")
    v_takeaways = "\n- " + "\n- ".join(active_video.get("key_takeaways", []))

    sys_prompt = f"""You are MICHAEL, an expert Indian stock market mentor, financial analyst, and interactive AI tutor inside the QUEST Education Platform.
You are actively helping a learner studying the following video lesson:
- Title: "{v_title}"
- Creator/Channel: {v_creator}
- Module: {v_module}
- Language Track: {v_lang}
- Lesson Summary: {v_summary}
- Key Takeaways:{v_takeaways}

YOUR INSTRUCTIONS:
1. Clear the student's doubt with precision, encouragement, and practical insight.
2. Explain complex financial jargon (like Demat, P/E, EPS, CAGR, Stop Loss, SEBI, NIFTY 50, Mutual Funds, Asset Allocation, NAV, etc.) using simple, real-world Indian examples.
3. If the user asks in Hindi or Hinglish, respond in natural, friendly Hindi/Hinglish. If in English, reply in crisp English.
4. If asked to quiz, ask 3 short, relevant multiple-choice questions with answers explained.
5. If asked how to apply this, explain how they can practice it using the Virtual Trading simulator in QUEST (with their starting ₹15,000 balance).
6. Keep formatting neat with clean bullet points and bold key terms. Never invent fake stock prices.
"""

    if api_key and provider == "groq":
        try:
            msgs = [{"role": "system", "content": sys_prompt}]
            for h in history[-5:]:
                msgs.append({"role": "user" if h["role"] == "user" else "assistant", "content": h["text"]})
            msgs.append({"role": "user", "content": query})
            
            req_data = json.dumps({
                "model": "openai/gpt-oss-120b",
                "messages": msgs,
                "temperature": 0.6,
                "max_tokens": 800
            }).encode("utf-8")
            
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "QUEST-App/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["choices"][0]["message"]["content"].strip()
        except Exception as e:
            pass

    if api_key and provider == "gemini":
        try:
            full_prompt = sys_prompt + "\n\n"
            for h in history[-5:]:
                full_prompt += f"{'User' if h['role']=='user' else 'MICHAEL'}: {h['text']}\n"
            full_prompt += f"User: {query}\nMICHAEL:"
            
            payload = json.dumps({
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"temperature": 0.6, "maxOutputTokens": 800}
            }).encode("utf-8")
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=25) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            pass

    # Intelligent Fallback Knowledge Engine (Context-Aware Offline Mode)
    q_low = query.lower()
    if "simple" in q_low or "explain" in q_low or "summary" in q_low:
        return f"""**⚡ MICHAEL's Concept Breakdown for "{v_title}":**

• **Core Big Picture**: {v_summary}
• **Why it matters for you**: Understanding this allows you to avoid costly beginner traps in Indian markets and compound wealth steadily.
• **Key Pillar 1**: {active_video.get('key_takeaways', ['Start early and stay consistent'])[0]}
• **Key Pillar 2**: {active_video.get('key_takeaways', ['Manage your risk before chasing returns'])[1] if len(active_video.get('key_takeaways', [])) > 1 else 'Always diversify your holdings.'}

*Pro Tip*: Try placing a mock order in your **Virtual Trading** tab to see how this works without risking real capital!"""

    elif "example" in q_low or "indian" in q_low or "market" in q_low:
        return f"""**⚡ Real-World Indian Market Context:**

• **Relating to Nifty & BSE**: When creators like {v_creator} discuss `{v_title}`, they emphasize real market dynamics seen in leading index stocks (e.g. Reliance, TCS, HDFC Bank).
• **Practical Scenario**: If you invest ₹1,000 monthly in an index fund yielding 12% CAGR, in 15 years you contribute ₹1.8 Lakhs, but your portfolio can grow to over ₹5 Lakhs due to compounding!
• **Execution**: Keep your asset allocation balanced between large-cap stability, mid-cap growth, and emergency liquidity."""

    elif "quiz" in q_low:
        return f"""**📝 Quick Practice Quiz on "{v_title}":**

**Q1. What is the primary purpose taught by {v_creator} in this lesson?**
a) To time the market every single hour
b) To follow a disciplined investing plan and manage risk
c) To borrow money to trade penny stocks

**Q2. When should an investor review their asset allocation?**
a) Only during extreme market crashes
b) Periodically (quarterly or annually) with a calm mindset
c) Never change anything for 50 years

*Think you know the answers? Reply with your choice or ask me to verify!* 🎯"""

    elif "virtual" in q_low or "portfolio" in q_low or "balance" in q_low:
        return f"""**💼 Applying this to your QUEST Virtual Portfolio:**

1. **Test the thesis**: Go to the **Virtual Trading** tab in the sidebar.
2. **Utilize your starting balance**: You have your paper trading balance ready. Pick 2-3 quality assets discussed in `{v_module}`.
3. **Set your Stop Loss & Target**: Before confirming the trade, calculate your risk-to-reward ratio as taught in this lesson!"""

    else:
        return f"""**⚡ MICHAEL AI Tutor:**

Regarding **"{query}"** in the context of *{v_title}* by {v_creator}:

• In Indian equities and financial planning, this concept emphasizes {active_video.get('key_takeaways', ['discipline and risk control'])[0].lower()}.
• **Next Action**: Review the key takeaways above, and feel free to ask me for definitions of any specific terms or how to practice this in Virtual Trading!"""

# ──────────────────────────────────────────────────────────────────────────────
# Main Render Function
# ──────────────────────────────────────────────────────────────────────────────

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


def render(user_info):
    catalog = _load_catalog()
    if not catalog:
        st.error("Education video catalog could not be loaded.")
        return

    # User progress & state
    progress = edu_db.load_progress()
    total_xp = progress.get("total_xp", 0)
    bookmarks = progress.get("bookmarks", [])
    completed_videos = progress.get("completed_articles", [])

    # Current Language Selection
    if "edu_video_lang" not in st.session_state:
        st.session_state.edu_video_lang = "en"
    
    current_lang = st.session_state.edu_video_lang

    # Flatten all videos for current language from catalog topics
    all_videos = []
    for mod in catalog:
        m_title = mod.get("module_title", "")
        m_id = mod.get("module_id", "")
        cat_color = mod.get("cat_color", "#3b82f6")
        cat_name = mod.get("category", "Basics")
        for t_idx, topic_obj in enumerate(mod.get("topics", [])):
            v_data = topic_obj.get(current_lang)
            if v_data:
                v_copy = dict(v_data)
                v_copy["module_title"] = m_title
                v_copy["module_id"] = m_id
                v_copy["cat_color"] = cat_color
                v_copy["category"] = cat_name
                v_copy["topic_index"] = t_idx
                v_copy["youtube_embed_id"] = v_data.get("youtube_id", "")
                all_videos.append(v_copy)

    # Active Video Selection
    if "active_edu_video_id" not in st.session_state or not st.session_state.active_edu_video_id:
        st.session_state.active_edu_video_id = all_videos[0]["id"] if all_videos else "module_1_t1_en"

    active_video = next((v for v in all_videos if v["id"] == st.session_state.active_edu_video_id), None)
    if not active_video and all_videos:
        active_video = all_videos[0]
        st.session_state.active_edu_video_id = active_video["id"]

    if not active_video:
        st.warning("No videos available for selected language category.")
        return

    # Find the corresponding other-language video for same topic & module
    other_lang = "hi" if current_lang == "en" else "en"
    other_lang_name = "हिन्दी / Hindi" if current_lang == "en" else "English"
    matching_other_video = None
    for mod in catalog:
        if mod.get("module_id") == active_video.get("module_id"):
            for t_idx, topic_obj in enumerate(mod.get("topics", [])):
                if t_idx == active_video.get("topic_index"):
                    matching_other_video = topic_obj.get(other_lang)
                    break

    # ──────────────────────────────────────────────────────────────────────────
    # Top Custom Styling
    # ──────────────────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .yt-top-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.2rem;
        padding-bottom: 0.8rem;
        border-bottom: 1px solid var(--q-border);
    }
    .yt-lang-pill-btn {
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .yt-video-frame-container {
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        border-radius: 16px;
        background: #000000;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        border: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 1rem;
    }
    .yt-video-frame-container iframe {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border: 0;
    }
    .yt-title-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 15px;
        margin-bottom: 0.8rem;
    }
    .yt-main-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: var(--q-text);
        line-height: 1.35;
    }
    .yt-creator-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid var(--q-border);
        margin-bottom: 1rem;
    }
    .yt-creator-info {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .yt-creator-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: #ffffff;
        font-size: 1.1rem;
    }
    .yt-creator-name {
        font-weight: 600;
        color: var(--q-text);
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .yt-desc-box {
        background: var(--q-surface-2);
        border: 1px solid var(--q-border);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 1.2rem;
    }
    .yt-desc-meta {
        font-weight: 600;
        font-size: 0.82rem;
        color: var(--q-text-2);
        margin-bottom: 6px;
    }
    .yt-desc-text {
        font-size: 0.88rem;
        color: var(--q-text-3);
        line-height: 1.5;
    }
    .yt-takeaway-item {
        font-size: 0.82rem;
        color: var(--q-text-2);
        margin: 4px 0;
        display: flex;
        align-items: baseline;
        gap: 6px;
    }
    .yt-card-thumb {
        width: 100%;
        height: 72px;
        border-radius: 10px;
        background: #0f172a;
        position: relative;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .yt-card-duration {
        position: absolute;
        bottom: 4px;
        right: 4px;
        background: rgba(0,0,0,0.8);
        padding: 1px 5px;
        border-radius: 4px;
        font-size: 0.68rem;
        font-weight: 600;
        color: #f8fafc;
    }
    .yt-card-details {
        padding-left: 8px;
    }
    .yt-card-title {
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--q-text);
        line-height: 1.3;
        margin-bottom: 3px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .yt-card-creator {
        font-size: 0.72rem;
        color: var(--q-text-3);
        display: flex;
        align-items: center;
        gap: 3px;
    }

    /* MICHAEL AI Assistant Container */
    .m-ai-box {
        background: rgba(13, 15, 28, 0.85);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(139, 92, 246, 0.35);
        border-radius: 16px;
        padding: 1.3rem;
        margin-top: 1.4rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    .m-ai-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.9rem;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    }
    .m-ai-avatar {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, #7c3aed, #a855f7);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        box-shadow: 0 0 12px rgba(168, 85, 247, 0.5);
    }
    </style>
    """, unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Top Bar: Language Switcher & Active Status
    # ──────────────────────────────────────────────────────────────────────────
    bar_col1, bar_col2 = st.columns([2.5, 1.5])
    
    with bar_col1:
        l_btn1, l_btn2 = st.columns(2)
        with l_btn1:
            is_en = current_lang == "en"
            if st.button("🇬🇧  English (100 Videos)", key="btn_lang_en", type="primary" if is_en else "secondary", use_container_width=True):
                st.session_state.edu_video_lang = "en"
                st.session_state.active_edu_video_id = ""
                st.rerun()
        with l_btn2:
            is_hi = current_lang == "hi"
            if st.button("🇮🇳  हिन्दी / Hindi (100 Videos)", key="btn_lang_hi", type="primary" if is_hi else "secondary", use_container_width=True):
                st.session_state.edu_video_lang = "hi"
                st.session_state.active_edu_video_id = ""
                st.rerun()

    with bar_col2:
        search_kw = st.text_input("🔍 Search 100 Topics", placeholder="Search topics, creators...", label_visibility="collapsed", key="search_topics_input")

    st.markdown("<div style='margin-bottom: 0.8rem;'></div>", unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Main Layout: 2 Columns (70% Player + MICHAEL AI Assistant / 30% Up Next)
    # ──────────────────────────────────────────────────────────────────────────
    col_player, col_upnext = st.columns([2.3, 1.1], gap="medium")

    # ══════════════════════════════════════════════════════════════════════════
    # Left Column: Video Player, Metadata, Actions, & MICHAEL AI Tutor
    # ══════════════════════════════════════════════════════════════════════════
    with col_player:
        v_id = active_video["id"]
        yt_embed_id = active_video.get("youtube_embed_id", "Xn7KWR9EOGQ")
        lang_badge = "English" if current_lang == "en" else "हिन्दी"

        # 1. YouTube Embedded Video Player
        st.markdown(f"""
        <div class="yt-video-frame-container">
            <iframe 
                src="https://www.youtube-nocookie.com/embed/{yt_embed_id}?autoplay=0&rel=0&modestbranding=1" 
                title="{active_video['title']}" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                allowfullscreen>
            </iframe>
        </div>
        """, unsafe_allow_html=True)

        # 2. Title & In-Player Language Cross-Switch
        st.markdown(f"""
        <div class="yt-title-row">
            <div class="yt-main-title">{active_video['title']}</div>
        </div>
        """, unsafe_allow_html=True)

        # Quick Switch to alternate language for same topic
        if matching_other_video:
            switch_lbl = f"🔄 Switch to {other_lang_name} version for this exact topic"
            if st.button(switch_lbl, key=f"btn_cross_lang_{v_id}", use_container_width=True):
                st.session_state.edu_video_lang = other_lang
                st.session_state.active_edu_video_id = matching_other_video["id"]
                st.rerun()

        # 3. Creator Bar & Actions
        c_info_col, c_acts_col = st.columns([1.2, 2.0])
        with c_info_col:
            creator_name = active_video.get("creator", "Finance Master")
            creator_initial = creator_name[0] if creator_name else "F"
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

            # Like Button
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
                comp_txt = "✅ Watched (+50 XP)" if is_watched else "🎓 +50 XP"
                if st.button(comp_txt, key=f"btn_comp_{v_id}", type="primary" if not is_watched else "secondary", disabled=is_watched, use_container_width=True):
                    if not is_watched:
                        new_xp = edu_db.complete_article(v_id, 50)
                        st.toast(f"🎉 Awesome! Lesson completed. +50 XP awarded! Total: {new_xp} XP", icon="⭐")
                        st.balloons()
                        st.rerun()

        # 4. Description Box with Real-World Takeaways
        views_txt = active_video.get("views", "320K")
        pub_txt = active_video.get("published", "Recently")
        takeaway_header = "Key Learning Takeaways:" if current_lang == "en" else "मुख्य निष्कर्ष (Key Takeaways):"
        
        desc_items_html = "".join([f'<div class="yt-takeaway-item"><span style="color:#10b981;">•</span> {tkw}</div>' for tkw in active_video.get("key_takeaways", [])])
        st.markdown(f"""
        <div class="yt-desc-box">
            <div class="yt-desc-meta">{views_txt} views &bull; {pub_txt} &bull; {active_video['module_title']} &bull; {lang_badge}</div>
            <div class="yt-desc-text">{active_video['summary']}</div>
            <div style="font-weight:700;font-size:0.85rem;color:var(--q-text);margin:10px 0 6px;">{takeaway_header}</div>
            {desc_items_html}
        </div>
        """, unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # 5. ⚡ MICHAEL AI ASSISTANT (Embedded Video Tutor & Doubt Solver)
        # ══════════════════════════════════════════════════════════════════════
        chat_state_key = f"edu_michael_history_{v_id}"
        if chat_state_key not in st.session_state:
            st.session_state[chat_state_key] = []

        v_history = st.session_state[chat_state_key]

        st.markdown(f"""
        <div class="m-ai-box">
            <div class="m-ai-header">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div class="m-ai-avatar">⚡</div>
                    <div>
                        <div style="font-weight:700;font-size:1.15rem;color:#ffffff;letter-spacing:-0.2px;">MICHAEL AI Assistant</div>
                        <div style="font-size:0.78rem;color:#c084fc;">Video Tutor & Doubt Solver &bull; Connected to: <em>{active_video['title'][:40]}...</em></div>
                    </div>
                </div>
                <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);border-radius:999px;padding:3px 10px;">
                    <div style="width:6px;height:6px;border-radius:50%;background:#10b981;box-shadow:0 0 6px #10b981;"></div>
                    <span style="font-size:0.72rem;font-weight:600;color:#34d399;">Context Active</span>
                </div>
            </div>
            <div style="font-size:0.86rem;color:#94a3b8;margin-bottom:12px;">
                Have a doubt or want a concept explained simply? Ask MICHAEL anything about this lesson or Indian investing.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Quick Starter Chips (1-Click Questions)
        st.markdown("<div style='font-size:0.78rem;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin:10px 0 6px;'>Quick Questions & Doubts:</div>", unsafe_allow_html=True)
        
        sq1, sq2, sq3, sq4 = st.columns(4)
        starter_query = None
        with sq1:
            if st.button("💡 Simple Summary", key=f"chip_sum_{v_id}", use_container_width=True):
                starter_query = f"Explain the main concepts of '{active_video['title']}' in very simple terms."
        with sq2:
            if st.button("📊 Indian Examples", key=f"chip_ex_{v_id}", use_container_width=True):
                starter_query = f"Give me real-world Indian stock market examples for '{active_video['title']}'."
        with sq3:
            if st.button("❓ Quiz Me (3 Qs)", key=f"chip_quiz_{v_id}", use_container_width=True):
                starter_query = f"Quiz me with 3 practice questions on '{active_video['title']}'."
        with sq4:
            if st.button("💼 Virtual Trading", key=f"chip_vt_{v_id}", use_container_width=True):
                starter_query = f"How can I apply '{active_video['title']}' inside my QUEST Virtual Trading portfolio?"

        # If user clicked starter chip
        if starter_query:
            ts = datetime.datetime.now().strftime("%H:%M")
            v_history.append({"role": "user", "text": starter_query, "ts": ts})
            with st.spinner("⚡ MICHAEL is analyzing video context and answering..."):
                reply = _ask_michael_video_ai(starter_query, active_video, v_history)
            v_history.append({"role": "michael", "text": reply, "ts": datetime.datetime.now().strftime("%H:%M")})
            st.session_state[chat_state_key] = v_history
            st.rerun()

        # Render Chat History
        if v_history:
            st.markdown("<div style='margin-top:14px;max-height:380px;overflow-y:auto;padding-right:6px;'>", unsafe_allow_html=True)
            for msg in v_history:
                if msg["role"] == "user":
                    clean_u_text = html.escape(msg['text']).replace('\n', '<br>')
                    st.markdown(f"""
                    <div style="display:flex;justify-content:flex-end;margin:8px 0;">
                        <div style="background:linear-gradient(135deg,#7c3aed,#9333ea);color:#ffffff;border-radius:14px 14px 2px 14px;padding:9px 14px;max-width:82%;font-size:0.88rem;box-shadow:0 4px 12px rgba(124,58,237,0.3);">
                            {clean_u_text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    formatted_ai_text = _format_ai_response_html(msg['text'])
                    st.markdown(f"""
                    <div style="display:flex;justify-content:flex-start;margin:10px 0;">
                        <div style="background:rgba(18,20,36,0.85);border:1px solid rgba(139,92,246,0.25);border-radius:14px 14px 14px 2px;padding:12px 16px;max-width:92%;color:#e2e8f0;font-size:0.88rem;line-height:1.5;box-shadow:0 6px 18px rgba(0,0,0,0.4);">
                            <div style="font-size:0.75rem;font-weight:700;color:#c084fc;margin-bottom:6px;display:flex;align-items:center;gap:6px;">
                                <span>⚡ MICHAEL AI</span> <span style="color:#64748b;font-size:0.68rem;font-weight:500;">{msg.get('ts', '')}</span>
                            </div>
                            <div>{formatted_ai_text}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Chat Input Form
        with st.form(key=f"edu_michael_form_{v_id}", clear_on_submit=True):
            in_col, btn_col = st.columns([4.2, 1.0])
            with in_col:
                user_doubt = st.text_input("Ask Doubt", placeholder=f"Ask MICHAEL any doubt about '{active_video['title'][:35]}...' ", label_visibility="collapsed")
            with btn_col:
                send_clicked = st.form_submit_button("Ask ⚡", type="primary", use_container_width=True)

            if send_clicked and user_doubt and user_doubt.strip():
                ts = datetime.datetime.now().strftime("%H:%M")
                v_history.append({"role": "user", "text": user_doubt.strip(), "ts": ts})
                with st.spinner("⚡ MICHAEL is thinking..."):
                    reply = _ask_michael_video_ai(user_doubt.strip(), active_video, v_history)
                v_history.append({"role": "michael", "text": reply, "ts": datetime.datetime.now().strftime("%H:%M")})
                st.session_state[chat_state_key] = v_history
                st.rerun()

        # Reset Chat Button
        if v_history:
            if st.button("🗑️ Clear Doubt History for this Video", key=f"btn_clear_ai_{v_id}"):
                st.session_state[chat_state_key] = []
                st.rerun()

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
                        <div style="font-size:0.68rem;color:var(--q-text-3);margin-top:2px;">{vid.get('views', '300K')} views &bull; {vid['category']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Click to play button
                btn_txt = "▶ Playing Now" if is_active else "Play Video"
                if st.button(btn_txt, key=f"yt_play_btn_{vid['id']}_{p_idx}", disabled=is_active, use_container_width=True):
                    st.session_state.active_edu_video_id = vid["id"]
                    st.rerun()
                st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

        if len(playlist_videos) > limit:
            if st.button("Load More Videos 🔽", key=f"btn_load_more_yt_{current_lang}", use_container_width=True):
                st.session_state.playlist_limit = limit + 8
                st.rerun()
