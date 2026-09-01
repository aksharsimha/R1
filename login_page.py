"""
QUEST Login Page — Complete UI Overhaul
========================================
Every single Streamlit default is overridden. This should look like
a custom-built web app, not a Streamlit page.
"""

import random
import streamlit as st

# ── Rotating copy ─────────────────────────────────────────────────────────────
_HEADLINES = [
    ("Welcome back", "Sign in to your portfolio dashboard"),
    ("Your money, measured.", "Sign in to see today's numbers"),
    ("Clarity over noise.", "Your portfolio, sign in to continue"),
    ("Know your risk first.", "Sign in to your portfolio dashboard"),
    ("Markets move. Stay ready.", "Sign in to pick up where you left off"),
]

_QUOTES = [
    ("Risk comes from not knowing what you're doing.", "Warren Buffett"),
    ("The investor's chief problem — and worst enemy — is likely to be himself.", "Benjamin Graham"),
    ("In the short run the market is a voting machine; in the long run, a weighing machine.", "Benjamin Graham"),
    ("Wide diversification is only required when investors do not understand what they are doing.", "Warren Buffett"),
    ("The four most dangerous words in investing are: 'this time it's different.'", "John Templeton"),
    ("Be fearful when others are greedy, and greedy when others are fearful.", "Warren Buffett"),
]


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_indices():
    """Best-effort live NIFTY 50 / SENSEX quotes. Returns [] on any failure."""
    out = []
    try:
        import yfinance as yf
        for label, tk in (("NIFTY 50", "^NSEI"), ("SENSEX", "^BSESN")):
            try:
                fi = yf.Ticker(tk).fast_info
                last = float(fi.last_price)
                prev = float(fi.previous_close)
                chg = (last - prev) / prev * 100 if prev else 0.0
                out.append((label, last, chg))
            except Exception:
                continue
    except Exception:
        return []
    return out


def render_login_page():
    from auth import (
        login_user, register_user, check_remember_me,
        save_remember_me, add_remembered_account, reset_password, clear_remember_me
    )

    if st.session_state.get("do_logout") or st.query_params.get("logged_out") == "true":
        st.session_state.auth_checked_remember = True
        remembered = None
    elif st.session_state.get("login_submit") or st.session_state.get("add_account_submit"):
        # Rule 3: Manual override. Skip auto-login if actively submitting a form.
        remembered = None
    else:
        # ── Check Remember Me ────────────────────────────────────────────────────
        remembered = check_remember_me()
        
    if remembered and not st.session_state.get("authenticated") and not st.session_state.get("account_add_mode"):
        # Guard against corrupted cookies with empty usernames
        _rem_username = remembered.get("username", "").strip()
        if not _rem_username:
            clear_remember_me()
            remembered = None
        else:
            # Hydrate full profile from Firestore (cookie only stores username/display_name)
            try:
                import firebase_db
                _profile = firebase_db.get_user_profile(_rem_username)
                _full_info = {
                    "username": _rem_username,
                    "display_name": _profile.get("display_name", remembered.get("display_name", _rem_username)),
                    "uid": _profile.get("uid", ""),
                    "email": _profile.get("email", ""),
                }
                if _profile.get("avatar"):
                    _full_info["avatar"] = _profile["avatar"]
            except Exception:
                _full_info = remembered
            st.session_state.authenticated = True
            st.session_state.user_info = _full_info
            st.session_state.just_logged_in = False
            # Preserve current URL page and workspace on refresh; fallback only if empty
            if "page" not in st.query_params or not st.query_params.get("page"):
                _existing_ws = st.query_params.get("workspace", "professional")
                st.query_params["page"] = "Library" if _existing_ws == "education" else "Overview"
                st.query_params["workspace"] = _existing_ws
            st.query_params.pop("return_to", None)
            st.query_params.pop("logged_out", None)
            st.rerun()

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"
    if "show_reset" not in st.session_state:
        st.session_state.show_reset = False

    # ══════════════════════════════════════════════════════════════════════════
    # NUCLEAR CSS — Override every Streamlit default & Polish Layout
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

        @keyframes qfade { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
        .qfade { animation: qfade .5s cubic-bezier(.22,.61,.36,1) both; }
        .qfade-1 { animation: qfade .5s cubic-bezier(.22,.61,.36,1) .06s both; }
        .qfade-2 { animation: qfade .5s cubic-bezier(.22,.61,.36,1) .12s both; }
        .qfade-3 { animation: qfade .5s cubic-bezier(.22,.61,.36,1) .18s both; }
        @media (prefers-reduced-motion: reduce) {
            .qfade, .qfade-1, .qfade-2, .qfade-3 { animation: none !important; }
        }

        /* ▓▓▓▓▓ TOTAL RESET & FLUSH TOP MARGINS ▓▓▓▓▓ */
        html, body {
            background: #07070e !important;
            overflow: hidden !important;
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }
        .stApp {
            background: #07070e !important;
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
            top: 0 !important;
        }
        *, *::before, *::after {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
            box-sizing: border-box !important;
        }
        ::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }

        /* ▓▓▓▓▓ KILL BLACK TOP BAR & ALL STREAMLIT CHROME COMPLETELY ▓▓▓▓▓ */
        header, [data-testid="stHeader"], .stAppHeader, div[data-testid="stHeader"],
        #MainMenu, .stDeployButton, footer, .stStatusWidget,
        div[data-testid="stToolbar"], div[data-testid="stDecoration"], [data-testid="stDecoration"] {
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            opacity: 0 !important;
            visibility: hidden !important;
            position: fixed !important;
            top: -9999px !important;
            pointer-events: none !important;
        }
        section[data-testid="stSidebar"], button[kind="header"] {
            display: none !important;
        }

        /* ▓▓▓▓▓ ROOT CONTAINERS — ABSOLUTE TOP 0, ZERO PADDING ▓▓▓▓▓ */
        .block-container, .main .block-container, section.main > div, section.main,
        div[data-testid="stAppViewContainer"], div[data-testid="stAppViewBlockContainer"],
        div[data-testid="stMainBlockContainer"], div.stMain,
        div[data-testid="stAppViewContainer"] > section.main,
        div[data-testid="stAppViewContainer"] > section.main > div.block-container {
            padding: 0 !important;
            padding-top: 0 !important;
            margin: 0 !important;
            margin-top: 0 !important;
            max-width: 100vw !important;
            width: 100vw !important;
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
        }

        div[data-testid="stAppViewBlockContainer"] > div[data-testid="stVerticalBlock"],
        div[data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"],
        .block-container > div[data-testid="stVerticalBlock"] {
            padding: 0 !important;
            padding-top: 0 !important;
            margin: 0 !important;
            margin-top: 0 !important;
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
            width: 100% !important;
            gap: 0 !important;
            row-gap: 0 !important;
        }

        /* Zero out any invisible script/style markdown containers in root block */
        div[data-testid="stAppViewBlockContainer"] > div[data-testid="stVerticalBlock"] > div:empty,
        div[data-testid="stAppViewBlockContainer"] > div[data-testid="stVerticalBlock"] > div[data-testid="element-container"]:has(style),
        div[data-testid="stAppViewBlockContainer"] > div[data-testid="stVerticalBlock"] > div[data-testid="element-container"]:has(script),
        div[data-testid="stAppViewBlockContainer"] > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:has(style),
        div[data-testid="stAppViewBlockContainer"] > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:has(script),
        div[data-testid="stElementContainer"]:has(style),
        div[data-testid="stElementContainer"]:has(script) {
            display: none !important;
            height: 0 !important;
            max-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            position: absolute !important;
            top: -9999px !important;
        }

        /* ▓▓▓▓▓ SPLIT SCREEN COLUMNS ▓▓▓▓▓ */
        div[data-testid="stHorizontalBlock"] {
            gap: 0 !important;
            height: 100vh !important;
            min-height: 100vh !important;
            max-height: 100vh !important;
            flex-wrap: nowrap !important;
            width: 100% !important;
            overflow: hidden !important;
        }
        div[data-testid="stColumn"] {
            padding: 0 !important;
            overflow: hidden !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }

        /* LEFT Column: Brand Gradient */
        div[data-testid="stHorizontalBlock"] > div:first-child {
            background: linear-gradient(160deg, #07070e 0%, #0c0c20 30%, #10103a 60%, #0c0c20 100%) !important;
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        /* RIGHT Column: Auth Form */
        div[data-testid="stHorizontalBlock"] > div:last-child {
            background: #0b0b16 !important;
            border-left: 1px solid rgba(255,255,255,0.04) !important;
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        /* Right column inner container — balanced vertical center */
        div[data-testid="stHorizontalBlock"] > div:last-child div[data-testid="stVerticalBlock"] {
            height: auto !important;
            max-height: 100vh !important;
            overflow: hidden !important;
            gap: 0 !important;
            row-gap: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            padding: 0.5rem 2rem !important;
            margin: 0 !important;
            width: 100% !important;
            max-width: 430px !important;
        }

        /* Zero out Streamlit element container margins */
        div[data-testid="stHorizontalBlock"] > div:last-child div[data-testid="element-container"],
        div[data-testid="stHorizontalBlock"] > div:last-child .element-container,
        div[data-testid="stHorizontalBlock"] > div:last-child [data-testid="stElementContainer"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
            padding: 0 !important;
        }

        /* Inner 2-column layout for side-by-side action buttons */
        div[data-testid="stHorizontalBlock"] > div:last-child div[data-testid="stHorizontalBlock"] {
            height: auto !important;
            min-height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            gap: 10px !important;
            margin: 4px 0 !important;
        }
        div[data-testid="stHorizontalBlock"] > div:last-child div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] {
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            padding: 0 !important;
        }

        /* ▓▓▓▓▓ FORM ▓▓▓▓▓ */
        div[data-testid="stForm"] {
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
            box-shadow: none !important;
            width: 100% !important;
            margin: 0 !important;
        }

        /* ▓▓▓▓▓ LABELS CLEANLY ABOVE INPUT BOXES ▓▓▓▓▓ */
        .stTextInput {
            margin-bottom: 5px !important;
        }
        .stTextInput label {
            display: block !important;
            margin: 0 0 3px 0 !important;
            padding: 0 !important;
            min-height: auto !important;
        }
        .stTextInput label p,
        .stTextInput label span {
            font-size: 0.68rem !important;
            font-weight: 700 !important;
            color: #94a3b8 !important;
            letter-spacing: 0.7px !important;
            text-transform: uppercase !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1.2 !important;
        }

        .stTextInput > div {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
        }

        /* Outer BaseWeb input container — THE ONLY BORDER */
        .stTextInput div[data-baseweb="input"],
        .stTextInput div[data-baseweb="base-input"] {
            background: rgba(255, 255, 255, 0.03) !important;
            border: 1px solid rgba(255, 255, 255, 0.09) !important;
            border-radius: 9px !important;
            padding: 0 12px !important;
            height: 38px !important;
            min-height: 38px !important;
            max-height: 38px !important;
            display: flex !important;
            align-items: center !important;
            box-sizing: border-box !important;
            box-shadow: none !important;
            outline: none !important;
            transition: all 0.2s ease !important;
        }

        .stTextInput div[data-baseweb="input"]:focus-within,
        .stTextInput div[data-baseweb="base-input"]:focus-within {
            border-color: #6366f1 !important;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
            background: rgba(99, 102, 241, 0.02) !important;
        }

        /* Inner input tag — ZERO BORDER, TRANSPARENT */
        .stTextInput input,
        .stTextInput input[type="text"],
        .stTextInput input[type="password"] {
            background: transparent !important;
            border: none !important;
            border-radius: 0 !important;
            outline: none !important;
            box-shadow: none !important;
            color: #f1f5f9 !important;
            font-size: 0.84rem !important;
            padding: 0 !important;
            margin: 0 !important;
            height: 100% !important;
            width: 100% !important;
        }
        .stTextInput input::placeholder {
            color: #334155 !important;
            font-size: 0.80rem !important;
        }

        /* ▓▓▓▓▓ PASSWORD EYE ICON (REPLACES 'VISIBILITY' TEXT COMPLETELY) ▓▓▓▓▓ */
        .stTextInput button,
        div[data-testid="stTextInput"] button,
        div[data-baseweb="input"] button,
        button[aria-label*="password"],
        button[aria-label*="Password"],
        div[data-testid="stTextInputPasswordToggle"] button {
            font-size: 0 !important;
            line-height: 0 !important;
            color: transparent !important;
            text-indent: -9999px !important;
            background: transparent !important;
            border: none !important;
            outline: none !important;
            width: 28px !important;
            height: 28px !important;
            min-width: 28px !important;
            max-width: 28px !important;
            padding: 0 !important;
            margin: 0 !important;
            cursor: pointer !important;
            overflow: hidden !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            position: relative !important;
            box-shadow: none !important;
        }

        .stTextInput button *,
        div[data-baseweb="input"] button * {
            display: none !important;
            visibility: hidden !important;
            font-size: 0 !important;
            color: transparent !important;
        }

        .stTextInput button::after,
        div[data-testid="stTextInput"] button::after,
        div[data-baseweb="input"] button::after,
        div[data-testid="stTextInputPasswordToggle"] button::after {
            content: '' !important;
            display: block !important;
            position: absolute !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            text-indent: 0 !important;
            width: 17px !important;
            height: 17px !important;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%23818cf8' stroke-width='2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M15 12a3 3 0 11-6 0 3 3 0 016 0z'/%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z'/%3E%3C/svg%3E") !important;
            background-repeat: no-repeat !important;
            background-position: center !important;
            background-size: contain !important;
            opacity: 0.8 !important;
            pointer-events: none !important;
            visibility: visible !important;
        }
        .stTextInput button:hover::after {
            opacity: 1 !important;
        }

        /* ▓▓▓▓▓ CHECKBOX ▓▓▓▓▓ */
        .stCheckbox {
            margin: 2px 0 6px 0 !important;
        }
        .stCheckbox label { color: #475569 !important; font-size: 0.74rem !important; }
        .stCheckbox label span { color: #475569 !important; font-size: 0.74rem !important; }

        /* ▓▓▓▓▓ PRIMARY BUTTON (Sign In) ▓▓▓▓▓ */
        div[data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #7c3aed 100%) !important;
            border: none !important;
            border-radius: 9px !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            padding: 0 !important;
            width: 100% !important;
            height: 36px !important;
            letter-spacing: 0.02em !important;
            transition: all 0.25s ease !important;
            box-shadow: 0 4px 14px -3px rgba(99,102,241,0.4) !important;
            cursor: pointer !important;
        }
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%) !important;
            box-shadow: 0 6px 20px -4px rgba(99,102,241,0.5) !important;
            transform: translateY(-1px) !important;
        }

        /* ▓▓▓▓▓ SECONDARY BUTTONS (Forgot PW, Create Account, Live Demo) ▓▓▓▓▓ */
        .stButton {
            margin: 2px 0 !important;
        }
        .stButton > button {
            background: rgba(255,255,255,0.02) !important;
            border: 1px solid rgba(99,102,241,0.2) !important;
            border-radius: 9px !important;
            color: #818cf8 !important;
            font-weight: 500 !important;
            font-size: 0.76rem !important;
            padding: 0 12px !important;
            height: 34px !important;
            transition: all 0.2s ease !important;
            width: 100% !important;
            cursor: pointer !important;
        }
        .stButton > button:hover {
            background: rgba(99,102,241,0.08) !important;
            border-color: rgba(99,102,241,0.4) !important;
            color: #a78bfa !important;
            transform: translateY(-1px) !important;
        }

        /* ▓▓▓▓▓ ERROR ALERTS ▓▓▓▓▓ */
        div[data-testid="stAlert"] {
            background: rgba(239,68,68,0.06) !important;
            border: 1px solid rgba(239,68,68,0.15) !important;
            border-radius: 8px !important;
            color: #fca5a5 !important;
            padding: 6px 10px !important;
            font-size: 0.74rem !important;
        }

        /* ▓▓▓▓▓ MOBILE RESPONSIVENESS ▓▓▓▓▓ */
        @media (max-width: 860px) {
            div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                flex-direction: column !important;
                min-height: auto !important;
                max-height: none !important;
                height: auto !important;
                overflow-y: auto !important;
            }
            div[data-testid="stColumn"] {
                min-width: 100% !important;
                max-width: 100% !important;
                width: 100% !important;
                height: auto !important;
                max-height: none !important;
            }
            div[data-testid="stHorizontalBlock"] > div:first-child {
                min-height: auto !important;
                height: auto !important;
                padding: 1.25rem 1rem !important;
            }
            div[data-testid="stHorizontalBlock"] > div:last-child {
                height: auto !important;
                max-height: none !important;
                padding: 1.5rem 1.2rem !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    # Nuclear DOM removal: kills the top black bar AND suppresses visibility text
    st.html("""
    <script>
    (function() {
        // Selectors for the top-bar and any Streamlit chrome that creates space at the top
        var TOP_BAR_SELECTORS = [
            '[data-testid="stDecoration"]',
            '[data-testid="stHeader"]',
            '[data-testid="stToolbar"]',
            '[data-testid="stStatusWidget"]',
            '.stAppHeader',
            'header[data-testid="stHeader"]',
            'div[data-testid="stDecoration"]',
            'div[data-testid="stHeader"]',
        ];

        function nukeTopBar() {
            TOP_BAR_SELECTORS.forEach(function(sel) {
                document.querySelectorAll(sel).forEach(function(el) {
                    el.style.cssText = 'display:none!important;height:0!important;min-height:0!important;max-height:0!important;padding:0!important;margin:0!important;overflow:hidden!important;position:fixed!important;top:-9999px!important;opacity:0!important;pointer-events:none!important;';
                    el.setAttribute('aria-hidden', 'true');
                });
            });
            // Also nuke any fixed/sticky element at top:0 that is less than 80px tall and has a dark/black background
            document.querySelectorAll('body > div, body > header, body > nav, .stApp > *, [data-testid="stAppViewContainer"] > *:not(section)').forEach(function(el) {
                var style = window.getComputedStyle(el);
                var rect = el.getBoundingClientRect();
                var bg = style.backgroundColor;
                // Kill elements: fixed/sticky, sitting at top < 10px, height < 80px, dark background
                if ((style.position === 'fixed' || style.position === 'sticky') && rect.top < 10 && rect.height < 80) {
                    el.style.cssText += 'display:none!important;height:0!important;';
                }
            });
        }

        function removeVisibilityText() {
            var buttons = document.querySelectorAll('.stTextInput button, div[data-baseweb="input"] button');
            buttons.forEach(function(b) {
                if (b.childNodes) {
                    for (var i = 0; i < b.childNodes.length; i++) {
                        if (b.childNodes[i].nodeType === 3) {
                            b.childNodes[i].nodeValue = '';
                        }
                    }
                }
            });
        }

        function runAll() {
            nukeTopBar();
            removeVisibilityText();
        }

        // Run immediately
        runAll();
        // Run again after DOM settles
        setTimeout(runAll, 100);
        setTimeout(runAll, 500);
        setTimeout(runAll, 1000);

        // Keep watching for dynamic re-injection
        var obs = new MutationObserver(runAll);
        obs.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """)


    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT
    # ══════════════════════════════════════════════════════════════════════════
    left, right = st.columns([1.1, 0.9], gap="small")

    # ── LEFT: Brand Panel ────────────────────────────────────────────────────
    with left:
        st.html("""
        <div class="q-brand-container" style="
            height: 100vh;
            max-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem 2.5rem;
            position: relative;
            overflow: hidden;
            font-family: 'Inter', -apple-system, sans-serif;
            box-sizing: border-box;
            width: 100%;
        ">
            <div style="position:absolute;width:400px;height:400px;border-radius:50%;background:radial-gradient(circle,rgba(99,102,241,0.15),transparent 70%);top:-80px;left:-100px;filter:blur(80px);"></div>
            <div style="position:absolute;width:350px;height:350px;border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,0.12),transparent 70%);bottom:-60px;right:-80px;filter:blur(80px);"></div>

            <div style="position:relative;z-index:2;max-width:400px;">
                <div style="font-size:2.2rem;margin-bottom:0.2rem;line-height:1;">⚡</div>
                <h1 style="
                    font-size:2.6rem;
                    font-weight:900;
                    letter-spacing:-1.5px;
                    margin:0 0 0.3rem 0;
                    line-height:1;
                    background:linear-gradient(135deg, #ffffff 0%, #94a3b8 100%);
                    -webkit-background-clip:text;
                    -webkit-text-fill-color:transparent;
                    font-family: 'Inter', sans-serif;
                ">QUEST</h1>
                <p style="
                    font-size:0.68rem;
                    color:#475569;
                    letter-spacing:2.5px;
                    text-transform:uppercase;
                    margin:0 0 1.6rem 0;
                    font-weight:500;
                    line-height:1.5;
                ">Quantitative Unified<br>Equity Surveillance Tracker</p>

                <div class="qfade-1" style="display:flex;flex-direction:column;gap:8px;">
                    <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;">
                        <div style="width:32px;height:32px;border-radius:8px;background:rgba(99,102,241,0.1);display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;">📊</div>
                        <div>
                            <div style="font-size:0.82rem;font-weight:600;color:#e2e8f0;margin-bottom:1px;">Real-Time Analytics</div>
                            <div style="font-size:0.72rem;color:#475569;line-height:1.3;">Live P&amp;L, composite risk scoring &amp; market data</div>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;">
                        <div style="width:32px;height:32px;border-radius:8px;background:rgba(139,92,246,0.1);display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;">🧠</div>
                        <div>
                            <div style="font-size:0.82rem;font-weight:600;color:#e2e8f0;margin-bottom:1px;">Self-Learning Forecasts</div>
                            <div style="font-size:0.72rem;color:#475569;line-height:1.3;">EWMA predictions that improve with every trade</div>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:10px;">
                        <div style="width:32px;height:32px;border-radius:8px;background:rgba(34,211,238,0.1);display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;">🔐</div>
                        <div>
                            <div style="font-size:0.82rem;font-weight:600;color:#e2e8f0;margin-bottom:1px;">Isolated &amp; Secure</div>
                            <div style="font-size:0.72rem;color:#475569;line-height:1.3;">Each user gets their own encrypted portfolio space</div>
                        </div>
                    </div>
                </div>

                <div style="margin-top:1.2rem;padding-top:0.8rem;border-top:1px solid rgba(255,255,255,0.04);">
                    <div style="font-size:0.65rem;color:#334155;letter-spacing:1px;text-transform:uppercase;font-weight:500;">Built for Indian markets · NSE &amp; BSE</div>
                </div>
            </div>
        </div>
        """)

    # ── RIGHT: Auth Form ─────────────────────────────────────────────────────
    with right:
        if st.session_state.show_reset:
            _render_reset(reset_password)
        elif st.session_state.auth_mode == "login":
            _render_login(login_user, save_remember_me)
        else:
            _render_signup(register_user, login_user, save_remember_me)


    st.stop()


def render_add_account_page(return_to: str = "Overview") -> None:
    """Render an authenticated user's isolated account-addition screen."""
    from auth import add_remembered_account, login_user

    st.markdown("""
    <style>
        .q-add-account { max-width: 520px; margin: 7vh auto 0; }
        .q-add-account h1 { color: var(--q-text); font-size: 2rem; margin-bottom: 4px; }
        .q-add-account p { color: var(--q-text-3); margin-top: 0; }
    </style>
    <div class="q-add-account">
        <h1>Add account</h1>
        <p>Sign in to add another account to this device.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Back", key="add_account_back"):
        st.query_params["page"] = return_to or "Overview"
        st.query_params.pop("return_to", None)
        st.rerun()

    with st.form("add_account_form", clear_on_submit=False, border=False):
        email = st.text_input("Email", placeholder="Enter your email", key="add_account_email")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="add_account_password")
        submitted = st.form_submit_button("Sign In", use_container_width=True, key="add_account_submit")

    if submitted:
        success, message, user_info = login_user(email, password)
        if success and user_info:
            # Rule 1 & 4: Clean state for isolated mode
            for k in ["firebase_hydrated", "show_risk_breakdown", "_sentiment_score", "_sentiment_neg_count", "_sentiment_ts", "do_logout", "_analysis_df", "_analysis_summary", "_analysis_ts"]:
                if k in st.session_state:
                    del st.session_state[k]
                    
            add_remembered_account(user_info["username"], user_info.get("display_name"))
            st.session_state.authenticated = True
            st.session_state.user_info = user_info
            st.session_state.firebase_hydrated = False
            st.session_state.just_logged_in = True
            st.query_params["page"] = "Overview"
            st.query_params.pop("return_to", None)
            st.rerun()
        else:
            st.error(message)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN FORM
# ══════════════════════════════════════════════════════════════════════════

def _render_login(login_user, save_remember_me):
    from auth import add_remembered_account

    # Live index ticker — individual separate pill boxes in top right (like image 2 & 4)
    _idx = _fetch_indices()
    if _idx:
        _chips = []
        for _lbl, _val, _chg in _idx:
            _c = "#34d399" if _chg >= 0 else "#f87171"
            _arrow = "▲" if _chg >= 0 else "▼"
            _chips.append(
                f"<div style='display:inline-flex;align-items:center;gap:6px;padding:3px 8px;border:1px solid rgba(255,255,255,0.07);"
                f"border-radius:6px;background:rgba(255,255,255,0.025);white-space:nowrap;'>"
                f"<span style='color:#64748b;font-size:0.60rem;letter-spacing:0.4px;font-weight:600;'>{_lbl}</span> "
                f"<span style='color:#f1f5f9;font-family:monospace;font-size:0.68rem;font-weight:600;'>{_val:,.2f}</span> "
                f"<span style='color:{_c};font-family:monospace;font-size:0.65rem;font-weight:600;'>{_arrow} {abs(_chg):.2f}%</span>"
                f"</div>"
            )
        _chips_html = "".join(_chips)
        st.markdown(
            f"<div class='qfade' style='display:flex;align-items:center;justify-content:flex-end;gap:6px;margin-bottom:0.4rem;width:100%;'>{_chips_html}</div>",
            unsafe_allow_html=True,
        )

    # Header (rotating copy)
    _hl, _sub = random.choice(_HEADLINES)
    st.markdown(f"""
    <div class="qfade" style="margin-bottom:0.5rem;">
        <h2 style="font-size:1.30rem;font-weight:700;color:#f1f5f9;margin:0 0 2px 0;letter-spacing:-0.5px;">
            {_hl}
        </h2>
        <p style="font-size:0.75rem;color:#64748b;margin:0;font-weight:400;">
            {_sub}
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False, border=False):
        # Email with clean floating label
        email = st.text_input("EMAIL", placeholder="Enter your email", key="le")

        # Password with clean floating label
        password = st.text_input("PASSWORD", type="password", placeholder="Enter your password", key="lp")

        # Remember me
        remember = st.checkbox("Remember me on this device", value=True, key="lr")

        # Submit
        submitted = st.form_submit_button("Sign In", use_container_width=True, key="login_submit")

        if submitted:
            success, message, user_info = login_user(email, password)
            if success:
                # Rule 1: Clean old state to prevent contamination
                for k in ["firebase_hydrated", "show_risk_breakdown", "_sentiment_score", "_sentiment_neg_count", "_sentiment_ts", "do_logout", "_analysis_df", "_analysis_summary", "_analysis_ts"]:
                    if k in st.session_state:
                        del st.session_state[k]
                
                st.session_state.authenticated = True
                st.session_state.user_info = user_info
                st.session_state.remember_me = remember
                if remember:
                    add_remembered_account(user_info["username"], user_info.get("display_name"))
                st.session_state.account_add_mode = False
                st.session_state.just_logged_in = True
                st.query_params["page"] = "Overview"
                st.query_params.pop("return_to", None)
                st.rerun()
            else:
                st.error(message)

    # Forgot password (styled with comfortable width)
    st.markdown('<div style="text-align:left;margin:3px 0 5px 0;width:auto;display:inline-block;">', unsafe_allow_html=True)
    if st.button("Forgot password?", key="forgot_pw", use_container_width=False):
        st.session_state.show_reset = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Divider
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin:6px 0 5px 0;">
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.06);"></div>
        <span style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:2px;font-weight:500;">OR</span>
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.06);"></div>
    </div>
    """, unsafe_allow_html=True)

    # Side-by-side action buttons: Create free account on left, Try live demo on right
    c1, c2 = st.columns(2, gap="small")
    with c1:
        if st.button("Create free account", key="to_signup", use_container_width=True):
            st.session_state.auth_mode = "signup"
            st.rerun()

    with c2:
        if st.button("🛰️ Try a live demo", key="try_demo", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.user_info = {
                "username": "demo_guest",
                "display_name": "Demo User",
                "email": "demo@quest.local",
            }
            st.session_state.just_logged_in = True
            st.query_params["page"] = "Overview"
            st.query_params.pop("return_to", None)
            st.rerun()

    # Exact original Benjamin Graham quote
    st.markdown(
        f"<div class='qfade' style='margin-top:0.8rem;padding:7px 10px;border-left:2px solid #6366f1;"
        f"background:rgba(255,255,255,0.02);border-radius:0 6px 6px 0;'>"
        f"<div style='font-size:0.72rem;color:#94a3b8;font-style:italic;line-height:1.35;'>“In the short run the market is a voting machine; in the long run, a weighing machine.”</div>"
        f"<div style='font-size:0.63rem;color:#475569;margin-top:3px;font-weight:500;'>— Benjamin Graham</div></div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SIGNUP FORM
# ══════════════════════════════════════════════════════════════════════════════

def _render_signup(register_user, login_user, save_remember_me):
    from auth import add_remembered_account

    st.markdown("""
    <div style="margin-bottom:0.8rem;">
        <h2 style="font-size:1.35rem;font-weight:700;color:#f1f5f9;margin:0 0 2px 0;letter-spacing:-0.5px;">
            Create account
        </h2>
        <p style="font-size:0.78rem;color:#475569;margin:0;font-weight:400;">
            Start tracking your portfolio in seconds
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("signup_form", clear_on_submit=False, border=False):
        st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#64748b;margin:0 0 2px 0;letter-spacing:0.5px;text-transform:uppercase;">Email</p>', unsafe_allow_html=True)
        email = st.text_input("e", placeholder="your@email.com", key="se", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#64748b;margin:6px 0 2px 0;letter-spacing:0.5px;text-transform:uppercase;">Display Name</p>', unsafe_allow_html=True)
        display_name = st.text_input("d", placeholder="How should we call you?", key="sd", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#64748b;margin:6px 0 2px 0;letter-spacing:0.5px;text-transform:uppercase;">Username</p>', unsafe_allow_html=True)
        username = st.text_input("u", placeholder="Choose a unique username", key="su", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#64748b;margin:6px 0 2px 0;letter-spacing:0.5px;text-transform:uppercase;">Password</p>', unsafe_allow_html=True)
        password = st.text_input("p", type="password", placeholder="Min. 6 characters", key="sp", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#64748b;margin:6px 0 2px 0;letter-spacing:0.5px;text-transform:uppercase;">Confirm Password</p>', unsafe_allow_html=True)
        confirm = st.text_input("c", type="password", placeholder="Re-enter your password", key="sc", label_visibility="collapsed")

        remember = st.checkbox("Remember me on this device", value=True, key="sr")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

        if submitted:
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                success, message = register_user(email, username, display_name, password)
                if success:
                    ok, _, user_info = login_user(email, password)
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.user_info = user_info
                        st.session_state.remember_me = remember
                        if remember:
                            add_remembered_account(user_info["username"], user_info.get("display_name"))
                        st.session_state.account_add_mode = False
                        st.session_state.just_logged_in = True
                        st.query_params["page"] = "Overview"
                        st.query_params.pop("return_to", None)
                        st.rerun()
                else:
                    st.error(message)

    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin:10px 0 8px 0;">
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.05);"></div>
        <span style="font-size:0.68rem;color:#334155;text-transform:uppercase;letter-spacing:2px;font-weight:500;">or</span>
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.05);"></div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Sign in instead", key="to_login", use_container_width=True):
        st.session_state.auth_mode = "login"
        st.rerun()

    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:0.8rem;opacity:0.35;">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <span style="font-size:0.65rem;color:#334155;">Secured with Firebase Authentication</span>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD RESET
# ══════════════════════════════════════════════════════════════════════════════

def _render_reset(reset_password):
    st.markdown("""
    <div style="margin-bottom:0.8rem;">
        <h2 style="font-size:1.35rem;font-weight:700;color:#f1f5f9;margin:0 0 2px 0;letter-spacing:-0.5px;">
            Reset password
        </h2>
        <p style="font-size:0.78rem;color:#475569;margin:0;font-weight:400;">
            We'll send a reset link to your email
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("reset_form", clear_on_submit=False, border=False):
        st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#64748b;margin:0 0 2px 0;letter-spacing:0.5px;text-transform:uppercase;">Email</p>', unsafe_allow_html=True)
        email = st.text_input("e", placeholder="Enter your email", key="re", label_visibility="collapsed")

        submitted = st.form_submit_button("Send Reset Link", use_container_width=True)

        if submitted and email:
            ok, msg = reset_password(email)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown('<div style="margin-top:10px;">', unsafe_allow_html=True)
    if st.button("← Back to sign in", key="back_to_login", use_container_width=True):
        st.session_state.show_reset = False
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
