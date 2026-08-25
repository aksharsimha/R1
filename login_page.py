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

    if st.session_state.get("do_logout"):
        clear_remember_me()
        st.session_state.auth_checked_remember = True
        st.session_state.do_logout = False
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

        @keyframes qfade { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
        .qfade { animation: qfade .6s cubic-bezier(.22,.61,.36,1) both; }
        .qfade-1 { animation: qfade .6s cubic-bezier(.22,.61,.36,1) .08s both; }
        .qfade-2 { animation: qfade .6s cubic-bezier(.22,.61,.36,1) .16s both; }
        .qfade-3 { animation: qfade .6s cubic-bezier(.22,.61,.36,1) .24s both; }
        @media (prefers-reduced-motion: reduce) {
            .qfade, .qfade-1, .qfade-2, .qfade-3 { animation: none !important; }
        }

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

        /* ▓▓▓▓▓ MOBILE RESPONSIVENESS ▓▓▓▓▓ */
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                flex-direction: column !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child {
                min-height: auto !important;
                padding: 2rem !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {
                min-height: auto !important;
                border-left: none !important;
            }
            div[data-testid="stColumn"]:last-child > div {
                padding: 2rem 1.5rem !important;
            }
            /* Hide the large blurred background circles on mobile to prevent overflow */
            div[data-testid="stColumn"]:first-child > div > div:nth-child(1),
            div[data-testid="stColumn"]:first-child > div > div:nth-child(2) {
                display: none !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT
    # ══════════════════════════════════════════════════════════════════════════
    left, right = st.columns([1.2, 0.8], gap="small")

    # ── LEFT: Brand Panel ────────────────────────────────────────────────────
    with left:
        st.html("""
        <div style="
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 3rem 2.5rem;
            position: relative;
            overflow: hidden;
            font-family: 'Inter', -apple-system, sans-serif;
        ">
            <div style="position:absolute;width:400px;height:400px;border-radius:50%;background:radial-gradient(circle,rgba(99,102,241,0.15),transparent 70%);top:-80px;left:-100px;filter:blur(80px);"></div>
            <div style="position:absolute;width:350px;height:350px;border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,0.12),transparent 70%);bottom:-60px;right:-80px;filter:blur(80px);"></div>

            <div style="position:relative;z-index:2;max-width:440px;">
                <div style="font-size:3.5rem;margin-bottom:0.3rem;line-height:1;">⚡</div>
                <h1 style="
                    font-size:3.5rem;
                    font-weight:900;
                    letter-spacing:-2px;
                    margin:0 0 0.6rem 0;
                    line-height:1;
                    background:linear-gradient(135deg, #ffffff 0%, #94a3b8 100%);
                    -webkit-background-clip:text;
                    -webkit-text-fill-color:transparent;
                    font-family: 'Inter', sans-serif;
                ">QUEST</h1>
                <p style="
                    font-size:0.75rem;
                    color:#475569;
                    letter-spacing:3px;
                    text-transform:uppercase;
                    margin:0 0 3rem 0;
                    font-weight:500;
                    line-height:1.6;
                ">Quantitative Unified<br>Equity Surveillance Tracker</p>

                <div class="qfade-1" style="display:flex;flex-direction:column;gap:12px;">
                    <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;">
                        <div style="width:38px;height:38px;border-radius:10px;background:rgba(99,102,241,0.1);display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;">📊</div>
                        <div>
                            <div style="font-size:0.85rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Real-Time Analytics</div>
                            <div style="font-size:0.75rem;color:#475569;line-height:1.4;">Live P&amp;L, composite risk scoring &amp; market data</div>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;">
                        <div style="width:38px;height:38px;border-radius:10px;background:rgba(139,92,246,0.1);display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;">🧠</div>
                        <div>
                            <div style="font-size:0.85rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Self-Learning Forecasts</div>
                            <div style="font-size:0.75rem;color:#475569;line-height:1.4;">EWMA predictions that improve with every trade</div>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;">
                        <div style="width:38px;height:38px;border-radius:10px;background:rgba(34,211,238,0.1);display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;">🔐</div>
                        <div>
                            <div style="font-size:0.85rem;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Isolated &amp; Secure</div>
                            <div style="font-size:0.75rem;color:#475569;line-height:1.4;">Each user gets their own encrypted portfolio space</div>
                        </div>
                    </div>
                </div>

                <div style="margin-top:2.5rem;padding-top:1.5rem;border-top:1px solid rgba(255,255,255,0.04);">
                    <div style="font-size:0.7rem;color:#334155;letter-spacing:1px;text-transform:uppercase;font-weight:500;">Built for Indian markets · NSE &amp; BSE</div>
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
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        success, message, user_info = login_user(email, password)
        if success and user_info:
            add_remembered_account(user_info["username"], user_info.get("display_name"))
            st.session_state.authenticated = True
            st.session_state.user_info = user_info
            st.session_state.firebase_hydrated = False
            st.query_params["page"] = "Overview"
            st.query_params.pop("return_to", None)
            st.rerun()
        else:
            st.error(message)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN FORM
# ══════════════════════════════════════════════════════════════════════════════

def _render_login(login_user, save_remember_me):
    from auth import add_remembered_account

    # Live index ticker (best-effort; hidden if unavailable)
    _idx = _fetch_indices()
    if _idx:
        _chips = ""
        for _lbl, _val, _chg in _idx:
            _c = "#34d399" if _chg >= 0 else "#f87171"
            _arrow = "▲" if _chg >= 0 else "▼"
            _chips += (
                f"<span style='margin-right:18px;'>"
                f"<span style='color:#64748b;font-size:0.72rem;letter-spacing:1px;'>{_lbl}</span> "
                f"<span style='color:#e2e8f0;font-family:monospace;'>{_val:,.2f}</span> "
                f"<span style='color:{_c};font-family:monospace;font-size:0.8rem;'>{_arrow} {abs(_chg):.2f}%</span></span>"
            )
        st.markdown(
            f"<div class='qfade' style='margin-bottom:1.2rem;padding:8px 12px;border:1px solid rgba(255,255,255,0.06);"
            f"border-radius:10px;background:rgba(255,255,255,0.02);font-size:0.85rem;white-space:nowrap;overflow:hidden;'>{_chips}</div>",
            unsafe_allow_html=True,
        )

    # Header (rotating copy)
    _hl, _sub = random.choice(_HEADLINES)
    st.markdown(f"""
    <div class="qfade" style="margin-bottom:2rem;">
        <h2 style="font-size:1.7rem;font-weight:700;color:#f1f5f9;margin:0 0 6px 0;letter-spacing:-0.5px;">
            {_hl}
        </h2>
        <p style="font-size:0.88rem;color:#475569;margin:0;font-weight:400;">
            {_sub}
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
                st.session_state.remember_me = remember
                if remember:
                    add_remembered_account(user_info["username"], user_info.get("display_name"))
                st.session_state.account_add_mode = False
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

    # Try a live demo — explore a sample portfolio, no signup
    if st.button("🛰️  Try a live demo", key="try_demo", use_container_width=True):
        st.session_state.authenticated = True
        st.session_state.user_info = {
            "username": "demo_guest",
            "display_name": "Demo User",
            "email": "demo@quest.local",
        }
        st.rerun()

    # Rotating finance quote
    _q, _who = random.choice(_QUOTES)
    st.markdown(
        f"<div class='qfade' style='margin-top:1.6rem;padding:14px 16px;border-left:2px solid rgba(99,102,241,0.4);"
        f"background:rgba(255,255,255,0.02);border-radius:0 8px 8px 0;'>"
        f"<div style='font-size:0.85rem;color:#94a3b8;font-style:italic;line-height:1.5;'>“{_q}”</div>"
        f"<div style='font-size:0.72rem;color:#475569;margin-top:6px;'>— {_who}</div></div>",
        unsafe_allow_html=True,
    )

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
    from auth import add_remembered_account

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
                        st.session_state.remember_me = remember
                        if remember:
                            add_remembered_account(user_info["username"], user_info.get("display_name"))
                        st.session_state.account_add_mode = False
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
