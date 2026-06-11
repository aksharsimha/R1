"""
QUEST Login Page — Complete UI Overhaul
========================================
Every single Streamlit default is overridden. This should look like
a custom-built web app, not a Streamlit page.
"""

import streamlit as st


def render_login_page():
    from auth import (
        login_user, register_user, check_remember_me,
        save_remember_me, reset_password,
    )

    # ── Check Remember Me ────────────────────────────────────────────────────
    if "auth_checked_remember" not in st.session_state:
        st.session_state.auth_checked_remember = True
        remembered = check_remember_me()
        if remembered:
            st.session_state.authenticated = True
            st.session_state.user_info = remembered
            st.rerun()

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"
    if "show_reset" not in st.session_state:
        st.session_state.show_reset = False

    # ══════════════════════════════════════════════════════════════════════════
    # NUCLEAR CSS — Override every Streamlit default
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

        /* ▓▓▓▓▓ TOTAL STREAMLIT RESET ▓▓▓▓▓ */
        html, body {
            background: #07070e !important;
            overflow-x: hidden !important;
        }
        .stApp {
            background: #07070e !important;
        }
        *, *::before, *::after {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        }

        /* Kill ALL Streamlit UI chrome */
        #MainMenu, .stDeployButton, footer,
        header[data-testid="stHeader"],
        .stStatusWidget,
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"] {
            display: none !important;
        }
        header {
            background: transparent !important;
            display: none !important;
        }

        /* Kill sidebar */
        section[data-testid="stSidebar"],
        button[kind="header"] {
            display: none !important;
        }

        /* ▓▓▓▓▓ NUKE ALL PADDING ▓▓▓▓▓ */
        .block-container,
        div[data-testid="stAppViewBlockContainer"] {
            padding: 0 !important;
            max-width: 100% !important;
            width: 100% !important;
        }

        .main .block-container {
            padding: 0 !important;
            max-width: 100vw !important;
        }

        section.main > div {
            padding: 0 !important;
            max-width: 100% !important;
        }

        /* ▓▓▓▓▓ COLUMNS = FULL SPLIT SCREEN ▓▓▓▓▓ */
        div[data-testid="stHorizontalBlock"] {
            gap: 0 !important;
            min-height: 100vh !important;
            flex-wrap: nowrap !important;
        }

        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            padding: 0 !important;
            overflow: hidden !important;
        }

        /* Left column = brand */
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child {
            background: linear-gradient(160deg, #07070e 0%, #0c0c20 30%, #10103a 60%, #0c0c20 100%) !important;
            min-height: 100vh !important;
            position: relative !important;
        }

        /* Right column = form */
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {
            background: #0b0b16 !important;
            border-left: 1px solid rgba(255,255,255,0.04) !important;
            min-height: 100vh !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        /* ▓▓▓▓▓ FORM TOTAL OVERRIDE ▓▓▓▓▓ */
        div[data-testid="stForm"] {
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
            box-shadow: none !important;
        }

        /* ▓▓▓▓▓ INPUT FIELDS ▓▓▓▓▓ */
        .stTextInput > div {
            background: transparent !important;
        }

        .stTextInput > div > div {
            background: transparent !important;
        }

        .stTextInput > div > div > input {
            background: rgba(255,255,255,0.03) !important;
            border: 1.5px solid rgba(255,255,255,0.08) !important;
            border-radius: 12px !important;
            color: #f1f5f9 !important;
            font-size: 0.92rem !important;
            padding: 14px 16px !important;
            height: auto !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            caret-color: #818cf8 !important;
            font-weight: 400 !important;
            letter-spacing: 0.01em !important;
        }

        .stTextInput > div > div > input:focus {
            border-color: #6366f1 !important;
            box-shadow: 0 0 0 3px rgba(99,102,241,0.12), 0 1px 2px rgba(0,0,0,0.2) !important;
            background: rgba(99,102,241,0.03) !important;
            outline: none !important;
        }

        .stTextInput > div > div > input::placeholder {
            color: #2a2a40 !important;
            font-weight: 400 !important;
        }

        /* Hide ALL default labels */
        .stTextInput > label,
        .stCheckbox > label > div:first-child,
        div[data-testid="stFormSubmitButton"] > button > div > p {
            font-family: 'Inter', sans-serif !important;
        }

        .stTextInput > label {
            display: none !important;
        }

        /* ▓▓▓▓▓ CHECKBOX ▓▓▓▓▓ */
        .stCheckbox {
            margin-top: 4px !important;
        }
        .stCheckbox label {
            color: #475569 !important;
            font-size: 0.82rem !important;
        }
        .stCheckbox label span {
            color: #475569 !important;
            font-size: 0.82rem !important;
        }

        /* ▓▓▓▓▓ PRIMARY BUTTON (SUBMIT) ▓▓▓▓▓ */
        div[data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #7c3aed 100%) !important;
            border: none !important;
            border-radius: 12px !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            padding: 14px 24px !important;
            width: 100% !important;
            letter-spacing: 0.02em !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 4px 15px -3px rgba(99,102,241,0.4), 0 1px 3px rgba(0,0,0,0.2) !important;
            cursor: pointer !important;
            margin-top: 8px !important;
            height: auto !important;
            min-height: 48px !important;
        }

        div[data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(135deg, #7c3aed 0%, #6366f1 50%, #8b5cf6 100%) !important;
            box-shadow: 0 8px 25px -5px rgba(99,102,241,0.5), 0 2px 6px rgba(0,0,0,0.3) !important;
            transform: translateY(-2px) !important;
        }

        div[data-testid="stFormSubmitButton"] > button:active {
            transform: translateY(0) !important;
            box-shadow: 0 2px 8px -2px rgba(99,102,241,0.3) !important;
        }

        /* ▓▓▓▓▓ SECONDARY BUTTON ▓▓▓▓▓ */
        .stButton > button {
            background: rgba(255,255,255,0.02) !important;
            border: 1.5px solid rgba(99,102,241,0.2) !important;
            border-radius: 12px !important;
            color: #818cf8 !important;
            font-weight: 500 !important;
            font-size: 0.88rem !important;
            padding: 12px 20px !important;
            transition: all 0.25s ease !important;
            width: 100% !important;
            cursor: pointer !important;
            height: auto !important;
            min-height: 44px !important;
        }

        .stButton > button:hover {
            background: rgba(99,102,241,0.08) !important;
            border-color: rgba(99,102,241,0.4) !important;
            color: #a78bfa !important;
            transform: translateY(-1px) !important;
        }

        /* ▓▓▓▓▓ ERROR ALERTS ▓▓▓▓▓ */
        div[data-testid="stAlert"] {
            background: rgba(239, 68, 68, 0.06) !important;
            border: 1px solid rgba(239, 68, 68, 0.15) !important;
            border-radius: 10px !important;
            color: #fca5a5 !important;
            padding: 12px 16px !important;
        }

        /* ▓▓▓▓▓ ELEMENT SPACING FIX ▓▓▓▓▓ */
        div[data-testid="stColumn"] > div > div > div {
            gap: 0 !important;
        }

        /* Right panel inner spacing */
        div[data-testid="stColumn"]:last-child > div {
            padding: 3rem 2.5rem !important;
            max-width: 420px !important;
            margin: 0 auto !important;
            width: 100% !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT
    # ══════════════════════════════════════════════════════════════════════════
    left, right = st.columns([1.2, 0.8], gap="small")

    # ── LEFT: Brand Panel ────────────────────────────────────────────────────
    with left:
        st.markdown("""
        <div style="
            position: relative;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4rem 3rem;
            overflow: hidden;
        ">
            <!-- Gradient orbs -->
            <div style="position:absolute;width:500px;height:500px;border-radius:50%;background:radial-gradient(circle,rgba(99,102,241,0.12),transparent 70%);top:-100px;left:-150px;filter:blur(60px);animation:drift1 25s ease-in-out infinite;"></div>
            <div style="position:absolute;width:400px;height:400px;border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,0.1),transparent 70%);bottom:-80px;right:-100px;filter:blur(60px);animation:drift2 20s ease-in-out infinite;"></div>
            <div style="position:absolute;width:250px;height:250px;border-radius:50%;background:radial-gradient(circle,rgba(34,211,238,0.06),transparent 70%);top:40%;left:50%;filter:blur(50px);animation:drift3 22s ease-in-out infinite;"></div>

            <style>
                @keyframes drift1 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(40px,-30px)} }
                @keyframes drift2 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(-30px,40px)} }
                @keyframes drift3 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(20px,20px)} }
                @keyframes line-draw { from{stroke-dashoffset:1500} to{stroke-dashoffset:0} }
                @keyframes area-fade { from{opacity:0} to{opacity:1} }
                @keyframes dot-pulse { 0%,100%{r:4;opacity:1} 50%{r:7;opacity:0.5} }
                @keyframes slide-up { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
            </style>

            <!-- Stock chart line -->
            <svg viewBox="0 0 600 200" preserveAspectRatio="none" style="position:absolute;bottom:80px;left:5%;width:90%;height:160px;opacity:0.5;">
                <defs>
                    <linearGradient id="lg1" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#6366f1" stop-opacity="0.6"/>
                        <stop offset="50%" stop-color="#a78bfa" stop-opacity="0.9"/>
                        <stop offset="100%" stop-color="#818cf8" stop-opacity="0.6"/>
                    </linearGradient>
                    <linearGradient id="lg2" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#6366f1" stop-opacity="0.08"/>
                        <stop offset="100%" stop-color="#6366f1" stop-opacity="0"/>
                    </linearGradient>
                </defs>
                <path d="M0,150 Q50,145 80,130 T160,100 T240,110 T320,60 T400,80 T480,35 T560,45 L600,30 L600,200 L0,200Z" fill="url(#lg2)" style="animation:area-fade 1s ease-out 2.5s both"/>
                <path d="M0,150 Q50,145 80,130 T160,100 T240,110 T320,60 T400,80 T480,35 T560,45 L600,30" fill="none" stroke="url(#lg1)" stroke-width="2" stroke-linecap="round" style="stroke-dasharray:1500;animation:line-draw 2.5s ease-out 0.3s both"/>
                <circle cx="600" cy="30" r="4" fill="#a78bfa" style="animation:dot-pulse 2s ease-in-out 3s infinite"/>
            </svg>

            <!-- Brand Content -->
            <div style="position:relative;z-index:2;max-width:460px;animation:slide-up 0.7s ease-out both">
                <div style="font-size:4.5rem;margin-bottom:0.5rem;line-height:1;">⚡</div>
                <h1 style="
                    font-size:4rem;
                    font-weight:900;
                    letter-spacing:-3px;
                    margin:0 0 0.8rem 0;
                    line-height:0.95;
                    background:linear-gradient(135deg, #ffffff 0%, #94a3b8 100%);
                    -webkit-background-clip:text;
                    -webkit-text-fill-color:transparent;
                ">QUEST</h1>
                <p style="
                    font-size:0.8rem;
                    color:#475569;
                    letter-spacing:4px;
                    text-transform:uppercase;
                    margin:0 0 3.5rem 0;
                    font-weight:500;
                    line-height:1.5;
                ">Quantitative Unified<br>Equity Surveillance Tracker</p>

                <!-- Feature Cards -->
                <div style="display:flex;flex-direction:column;gap:14px;">
                    <div style="
                        display:flex;align-items:center;gap:14px;
                        padding:16px 18px;
                        background:rgba(255,255,255,0.02);
                        border:1px solid rgba(255,255,255,0.05);
                        border-radius:14px;
                        transition:all 0.3s ease;
                        animation:slide-up 0.5s ease-out 0.15s both;
                    " onmouseover="this.style.background='rgba(99,102,241,0.05)';this.style.borderColor='rgba(99,102,241,0.12)';this.style.transform='translateX(6px)'" onmouseout="this.style.background='rgba(255,255,255,0.02)';this.style.borderColor='rgba(255,255,255,0.05)';this.style.transform='translateX(0)'">
                        <div style="width:40px;height:40px;border-radius:10px;background:rgba(99,102,241,0.1);display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0;">📊</div>
                        <div>
                            <div style="font-size:0.9rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Real-Time Analytics</div>
                            <div style="font-size:0.78rem;color:#475569;line-height:1.4;">Live P&L, composite risk scoring & market data</div>
                        </div>
                    </div>

                    <div style="
                        display:flex;align-items:center;gap:14px;
                        padding:16px 18px;
                        background:rgba(255,255,255,0.02);
                        border:1px solid rgba(255,255,255,0.05);
                        border-radius:14px;
                        transition:all 0.3s ease;
                        animation:slide-up 0.5s ease-out 0.3s both;
                    " onmouseover="this.style.background='rgba(139,92,246,0.05)';this.style.borderColor='rgba(139,92,246,0.12)';this.style.transform='translateX(6px)'" onmouseout="this.style.background='rgba(255,255,255,0.02)';this.style.borderColor='rgba(255,255,255,0.05)';this.style.transform='translateX(0)'">
                        <div style="width:40px;height:40px;border-radius:10px;background:rgba(139,92,246,0.1);display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0;">🧠</div>
                        <div>
                            <div style="font-size:0.9rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Self-Learning Forecasts</div>
                            <div style="font-size:0.78rem;color:#475569;line-height:1.4;">EWMA predictions that improve with every trade</div>
                        </div>
                    </div>

                    <div style="
                        display:flex;align-items:center;gap:14px;
                        padding:16px 18px;
                        background:rgba(255,255,255,0.02);
                        border:1px solid rgba(255,255,255,0.05);
                        border-radius:14px;
                        transition:all 0.3s ease;
                        animation:slide-up 0.5s ease-out 0.45s both;
                    " onmouseover="this.style.background='rgba(34,211,238,0.05)';this.style.borderColor='rgba(34,211,238,0.12)';this.style.transform='translateX(6px)'" onmouseout="this.style.background='rgba(255,255,255,0.02)';this.style.borderColor='rgba(255,255,255,0.05)';this.style.transform='translateX(0)'">
                        <div style="width:40px;height:40px;border-radius:10px;background:rgba(34,211,238,0.1);display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0;">🔐</div>
                        <div>
                            <div style="font-size:0.9rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Isolated & Secure</div>
                            <div style="font-size:0.78rem;color:#475569;line-height:1.4;">Each user gets their own encrypted portfolio space</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── RIGHT: Auth Form ─────────────────────────────────────────────────────
    with right:
        if st.session_state.show_reset:
            _render_reset(reset_password)
        elif st.session_state.auth_mode == "login":
            _render_login(login_user, save_remember_me)
        else:
            _render_signup(register_user, login_user, save_remember_me)


    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN FORM
# ══════════════════════════════════════════════════════════════════════════════

def _render_login(login_user, save_remember_me):
    # Header
    st.markdown("""
    <div style="margin-bottom:2rem;">
        <h2 style="font-size:1.7rem;font-weight:700;color:#f1f5f9;margin:0 0 6px 0;letter-spacing:-0.5px;">
            Welcome back
        </h2>
        <p style="font-size:0.88rem;color:#475569;margin:0;font-weight:400;">
            Sign in to your portfolio dashboard
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False, border=False):
        # Email
        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:0 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Email</p>', unsafe_allow_html=True)
        email = st.text_input("e", placeholder="Enter your email", key="le", label_visibility="collapsed")

        # Password
        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:16px 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Password</p>', unsafe_allow_html=True)
        password = st.text_input("p", type="password", placeholder="Enter your password", key="lp", label_visibility="collapsed")

        # Remember me
        remember = st.checkbox("Remember me on this device", value=True, key="lr")

        # Submit
        submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            success, message, user_info = login_user(email, password)
            if success:
                st.session_state.authenticated = True
                st.session_state.user_info = user_info
                if remember:
                    save_remember_me(user_info["username"])
                st.rerun()
            else:
                st.error(message)

    # Forgot password
    st.markdown('<div style="text-align:center;margin-top:8px;">', unsafe_allow_html=True)
    if st.button("Forgot password?", key="forgot_pw", use_container_width=False):
        st.session_state.show_reset = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Divider
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin:24px 0;">
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.05);"></div>
        <span style="font-size:0.72rem;color:#334155;text-transform:uppercase;letter-spacing:2px;font-weight:500;">or</span>
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.05);"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p style="text-align:center;font-size:0.85rem;color:#475569;margin:0 0 10px 0;">New to QUEST?</p>', unsafe_allow_html=True)
    if st.button("Create a free account", key="to_signup", use_container_width=True):
        st.session_state.auth_mode = "signup"
        st.rerun()

    # Footer
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-top:3rem;opacity:0.35;">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <span style="font-size:0.7rem;color:#334155;">Secured with Firebase Authentication</span>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIGNUP FORM
# ══════════════════════════════════════════════════════════════════════════════

def _render_signup(register_user, login_user, save_remember_me):
    st.markdown("""
    <div style="margin-bottom:2rem;">
        <h2 style="font-size:1.7rem;font-weight:700;color:#f1f5f9;margin:0 0 6px 0;letter-spacing:-0.5px;">
            Create account
        </h2>
        <p style="font-size:0.88rem;color:#475569;margin:0;font-weight:400;">
            Start tracking your portfolio in seconds
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("signup_form", clear_on_submit=False, border=False):
        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:0 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Email</p>', unsafe_allow_html=True)
        email = st.text_input("e", placeholder="your@email.com", key="se", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:16px 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Display Name</p>', unsafe_allow_html=True)
        display_name = st.text_input("d", placeholder="How should we call you?", key="sd", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:16px 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Username</p>', unsafe_allow_html=True)
        username = st.text_input("u", placeholder="Choose a unique username", key="su", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:16px 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Password</p>', unsafe_allow_html=True)
        password = st.text_input("p", type="password", placeholder="Min. 6 characters", key="sp", label_visibility="collapsed")

        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:16px 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Confirm Password</p>', unsafe_allow_html=True)
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
                        if remember:
                            save_remember_me(user_info["username"])
                        st.rerun()
                else:
                    st.error(message)

    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin:24px 0;">
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.05);"></div>
        <span style="font-size:0.72rem;color:#334155;text-transform:uppercase;letter-spacing:2px;font-weight:500;">or</span>
        <div style="flex:1;height:1px;background:rgba(255,255,255,0.05);"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p style="text-align:center;font-size:0.85rem;color:#475569;margin:0 0 10px 0;">Already have an account?</p>', unsafe_allow_html=True)
    if st.button("Sign in instead", key="to_login", use_container_width=True):
        st.session_state.auth_mode = "login"
        st.rerun()

    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-top:3rem;opacity:0.35;">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <span style="font-size:0.7rem;color:#334155;">Secured with Firebase Authentication</span>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD RESET
# ══════════════════════════════════════════════════════════════════════════════

def _render_reset(reset_password):
    st.markdown("""
    <div style="margin-bottom:2rem;">
        <h2 style="font-size:1.7rem;font-weight:700;color:#f1f5f9;margin:0 0 6px 0;letter-spacing:-0.5px;">
            Reset password
        </h2>
        <p style="font-size:0.88rem;color:#475569;margin:0;font-weight:400;">
            We'll send a reset link to your email
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("reset_form", clear_on_submit=False, border=False):
        st.markdown('<p style="font-size:0.8rem;font-weight:600;color:#64748b;margin:0 0 6px 0;letter-spacing:0.5px;text-transform:uppercase;">Email</p>', unsafe_allow_html=True)
        email = st.text_input("e", placeholder="Enter your email", key="re", label_visibility="collapsed")

        submitted = st.form_submit_button("Send Reset Link", use_container_width=True)

        if submitted and email:
            ok, msg = reset_password(email)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown('<div style="margin-top:16px;">', unsafe_allow_html=True)
    if st.button("← Back to sign in", key="back_to_login", use_container_width=True):
        st.session_state.show_reset = False
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
