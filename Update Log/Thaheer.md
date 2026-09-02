# Thaheer Update Log

## 2026-09-02

### ✉️ Chat System Gmail Email Notifications Delivery Fix
- **Fixed Google SMTP 501 HELO/EHLO Hostname Rejection**:
  - Resolved `501 5.5.4 HELO/EHLO argument invalid` errors by setting explicit `local_hostname='localhost'` on `smtplib.SMTP`, preventing Google SMTP from rejecting connections due to local Windows FQDN hostnames with invalid characters (`@`).
- **Port 587 STARTTLS & Port 465 SSL Resilient Fallback**:
  - Implemented dual-stage connection fallback in `chat_system.py`: tries Port 587 STARTTLS and automatically falls back to Port 465 SSL if Port 587 is blocked by network firewalls.
- **Multi-Source Credential Loading**:
  - Updated `_get_smtp_credentials` to load `SMTP_EMAIL` and `SMTP_PASSWORD` reliably across `st.secrets`, `.streamlit/secrets.toml`, and environment variables.
- **Asynchronous Background Delivery**:
  - Dispatched `_trigger_email_bg` in a daemon background thread (`threading.Thread(daemon=True)`), making chat message sending completely instantaneous without blocking the Streamlit UI.
- **Planner Task Reminder SMTP Fix**:
  - Updated `quest_app/tabs/planner.py` with the same `local_hostname='localhost'` and SSL fallback for task reminder email delivery.

### ⚡ Runtime Page Loading & Performance Overhaul
- **Non-Portfolio Fast-Path Routing**:
  - Added early route dispatch in `quest_app/main.py` for Education pages (*Learning Path*, *Knowledge Library*, *Leaderboard*, etc.) and Settings to render immediately, bypassing unnecessary portfolio calculations and news scraping.
- **Extended Cache TTL**:
  - Increased `_ANALYSIS_TTL` from 30 seconds to 180 seconds (3 minutes) and sentiment cache TTL to 600 seconds (10 minutes) in `quest_app/main.py`, eliminating lag on page clicks and tab switches.
- **Concurrent Portfolio Analysis**:
  - Refactored `analyze_portfolio` in `risk_analyzer.py` from a sequential asset loop to parallel `ThreadPoolExecutor` worker threads, drastically reducing analysis runtime from ~15s to ~1-3s.
- **Module-Level Streamlit Caching Optimization**:
  - Relocated nested `@st.cache_data` decorators from inside `render()` functions to top-level module scope in `overview_hero.py`, `projections.py`, and `risk_breakdown.py`, eliminating memory thrashing and cache misses on reruns.
- **Lightweight Tab Fallbacks**:
  - Added instant cached metric fallbacks for *Chat*, *Planner*, and *Activity* tabs.

### 🎥 Knowledge Library Module-to-Video Synchronization Architecture
- **Single Source of Truth (`catalog`)**:
  - Re-architected state to use indexed tracking (`edu_active_module_idx` and `edu_active_video_idx`) referencing `education_catalog.json` as the single source of truth without hardcoded IDs or stale duplicate state.
- **Module Dropdown Instant First-Video Auto-Load**:
  - Selecting any module (Module 1 through Module 10) from the dropdown immediately resets `edu_active_video_idx` to `0` and loads the **first video of that selected module** into the player.
  - Video title, thumbnail, creator, duration, description, takeaways, and YouTube embed ID/URL all update in real time to the selected module's first video.
  - "Up Next" sidebar playlist updates dynamically to list all 10 videos belonging to the active module, with index 0 highlighted as `▶ Playing Now`.
- **Intra-Module Video Selection**:
  - Clicking any other video in the playlist plays that video while preserving the active module state.
- **Cross-Language Topic Synchronization**:
  - Toggling between `🇬🇧 English (100 Videos)` and `🇮🇳 हिन्दी / Hindi (100 Videos)` preserves the exact module and topic index, loading the translation of the active video seamlessly.
- **Module 1 Topic 1 Video ID Alignment**:
  - Aligned Zerodha Varsity English masterclass (`GcZW24SkbHM`) and CA Rachana Ranade's Hindi masterclass (`Xn7KWR9EOGQ`) in `education_catalog.json`.

### 🧭 Environment Navigation State & Sub-Page Persistence
- **First Login / Initial Visit Default**:
  - Configured Environment → Education to strictly default to **Learning Path** on first login/visit (never hardcoded to Knowledge Library).
- **Per-User Sub-Page Memory Across Environment Switches**:
  - Implemented persistent user-scoped state tracking via `edu_db.get_last_education_section()` / `set_last_education_section()` and `edu_db.get_last_portfolio_section()` / `set_last_portfolio_section()`.
  - Switching between **Portfolio ↔ Education** seamlessly preserves and reopens the user's last selected sub-page (e.g. *Virtual Trading*, *Knowledge Library*, *Leaderboard*, *Badges*, *Tax Detective*, or *Learning Path*).
- **User-Scoped Isolation**:
  - Radio navigation keys and disk storage are scoped to the active `_username`, preventing cross-account state leakage when logging in as different users.
- **Hub & Settings Return Synchronization**:
  - Updated "Resume Learning →" in Main Hub and "← Dashboard" in Settings to automatically navigate to the user's last remembered active section.

---

## 2026-09-01

### ⚡ MICHAEL AI Video Study Assistant & Doubt Solver
- **Embedded In-Player AI Assistant**:
  - Integrated **MICHAEL AI Video Assistant** directly beneath the active video lesson in the **Knowledge Library** (`quest_app/tabs/education.py`).
  - **Context-Aware Video Mentorship**: Automatically injects complete video metadata (Title, Creator, Module, Language Track, Summary, and Key Takeaways) into the LLM system prompt.
  - **Bilingual Doubt Resolution**: Explains complex Indian financial market concepts (Demat, CAGR, Stop Loss, SEBI, P/E ratio, compounding, NAV, mutual funds, asset allocation) in crisp English or natural Hindi/Hinglish.
  - **Streamlined 1-Click Quick Doubt Chips**:
    - `💡 Simple Summary`: Generates a clear, beginner-friendly conceptual breakdown.
    - `📊 Indian Examples`: Provides real-world Indian market applications with Nifty 50, BSE, and leading index equities (Reliance, TCS, HDFC Bank).
  - **Interactive Chat Interface**:
    - Dark glassmorphism chat container with distinct user and AI message bubbles, timestamps, doubt input form, and chat history reset.
    - Powered by Groq / Gemini with an intelligent built-in pedagogical fallback knowledge engine.

### 🎨 Whitespace & UI Gap Elimination Fixes
- **Chat Markdown & Whitespace Parser (`_format_ai_response_html`)**:
  - Eliminated large empty vertical spaces in chat bubbles by collapsing duplicate/consecutive newlines (`\n{3,}`).
  - Replaced unformatted `white-space: pre-wrap` with structured paragraph spacing, tidy header tags (`margin: 6px 0 2px;`), and bullet points (`margin: 2px 0 2px 8px;`).
  - Implemented custom markdown table converter (`_render_html_table`) transforming raw pipes into native, modern dark tables (`<table>`, `<th>`, `<td>`) with compact padding and purple accent headers.
  - Applied across both the **Knowledge Library Video Tutor** (`quest_app/tabs/education.py`) and the **Portfolio Intelligence Assistant** (`quest_app/tabs/michael.py`).
- **Unified Video Description & Takeaways DOM Block**:
  - Grouped the description text and bulleted takeaways into a single closed HTML render container in `quest_app/tabs/education.py` to eliminate unclosed Streamlit container margins.
- **Import Resolution**:
  - Resolved `NameError: name 'html' is not defined` by adding `import html` and `import re` to `quest_app/tabs/education.py` and `quest_app/tabs/michael.py`.

### 📚 Knowledge Library Catalog Topic Extraction Fix
- Corrected the nested topic mapping in `quest_app/tabs/education.py` to accurately parse both the **100 English** and **100 Hindi** video lessons across all 10 Modules in `education_catalog.json`.
- Restored seamless video playback, in-player language switching, and lesson progress tracking.

### 🏠 Main Hub Switchboard UI (Real Data Driven & Streamlined)
- Connected all Hub card metrics directly to real user data (`edu_db` & `portfolio_ledger`):
  - **Professional Portfolio**: Markets Tracked (live portfolio holdings count), Watchlist (live assets count), Alerts (live portfolio warnings count from `analyze_portfolio`), and Last Updated (relative timestamp from latest ledger transaction).
  - **Games & Education**: Total XP, Next XP milestone, Level number, Virtual Trading Balance, and Achievements / completed articles (`completed_articles / 100`).
- **Removed Motivation Strip**: Completely removed the bottom motivation card (quote, streak, weekly goal, and view achievements button) per user specifications.
- **Fixed HTML Code Block Escaping**: Cleared all leading whitespace from HTML strings in `quest_app/tabs/hub.py` to prevent Streamlit's markdown parser from wrapping HTML in `<pre><code>` code blocks.

### 🧭 Sidebar Environment Switcher & Page Refresh State Preservation
- Added an **Environment Switcher** directly in the left sidebar (`💼 Portfolio` & `🎓 Education`).
- Enables 1-click seamless switching between **💼 Professional Portfolio** and **🎓 Games & Education** at any time without logging out or losing session state.
- **Persistent Page Refresh**: Fixed cookie auto-login and query param routing so that reloading or refreshing the browser retains the exact active page and workspace without resetting to Hub or Overview.
- Highlights the active environment with primary accent styling.
- Dynamically swaps navigation options and preserves URL query parameters (`workspace=professional` / `workspace=education`).
- Added a `🏠 Main Hub` return button at the bottom of the sidebar.

---

## 2026-08-31

### Bilingual Video Learning Hub (200 Curated Videos: 100 English + 100 Hindi)
- Built dual language category system supporting **English (100 Videos)** and **हिन्दी / Hindi (100 Videos)** across the identical 10 Modules and 100 Topics.
- **Direct Lesson Completion (+50 XP)**: Removed manual percentage buttons and 80% progress bar; users claim `🎓 +50 XP` upon completing the full video lesson.
- **Removed Follow Button & Notification Icons**: Removed the `+ Follow` button from the creator info bar and removed notification bell icons from both the top profile header and the left sidebar for a clean learning interface.
- **Fixed Embed Availability (100% Verified Playback)**: Validated all YouTube video IDs through the YouTube oEmbed API to eliminate all "Video unavailable" playback errors across both English and Hindi lanes.
- **Top Language Switcher**: Added 1-click toggle buttons (`English (100 Videos)` / `हिन्दी / Hindi (100 Videos)`) allowing learners to switch language categories anytime.
- **In-Player Topic Cross-Switch**: Added dynamic inline switcher to toggle between the English and Hindi lecture versions for the exact same topic (e.g. *Zerodha Varsity* ↔ *CA Rachana Ranade*).
- **200 Curated Videos Catalog (`quest_app/education_catalog.json`)**: Integrated all 10 Modules and 100 Topics with verified creators and direct working video IDs for both English and Hindi lanes.
- **Live User Likes (Starting at 0)**: Tracks genuine likes from logged-in users only.
- **Gamification**: Preserved bookmarking and `🎓 +50 XP` completion reward.

---

## 2026-08-28

### News AI Dashboard & Full Interactivity Overhaul
- Redesigned the News tab (`quest_app/tabs/news.py`) into the modern News AI Dashboard matching the user mockup.
- Swapped two-column layout so Latest News is placed on the Left and Market Overview on the Right.
- Removed top sentiment KPI metric cards and sentiment summary bar to streamline header and eliminate clutter.
- Built Market Overview panel with live NIFTY 50 and SENSEX metrics, sparklines, and market breadth (Advances / Declines / Unchanged).
- Made **🔥 Trending Market Topics** fully clickable with deep dive analysis dialogs covering catalysts, impacted stocks, and related news for `#NIFTY25K`, `#Q2Results`, `#RBIPolicy`, `#AITechRally`, `#GreenHydrogen`, `#DefencePSU`, `#AutoDemand`, and `#BankMergers`.
- Added **📅 Earnings & Dividends Calendar** integrated with Yahoo Finance to display upcoming quarter results release dates, consensus EPS estimates, and dividend ex-dates for user holdings and Indian market leaders.
- Built Latest News feed with live market articles from NSE benchmarks, category tags, thumbnails, read times, and `View All News →` modal.
- Removed notification icon from top header and preserved Search 🔍 and Profile 👤 quick actions.
- Built **2-Year Monthly Historical News & Sentiment Archive (2025 - 2026)** 📁 with individual month selection (`01 - January` through `12 - December`), year selector, and keyword/ticker search.

### Chat Avatars & Profile Pictures
- Replaced letter placeholders with actual user profile avatars across the Chat tab (`quest_app/tabs/chat.py`).
- Added cached profile and avatar rendering helpers (`_get_profile_cached`, `_render_avatar_html`) to load avatars from Firestore.
- Updated the Chat header to show the other participant's avatar image alongside a live status badge (`.chat-avatar-wrap`).
- Added avatar thumbnails to both received messages (left side) and sent messages (right side) in the message stream.
- Updated the Public Profile dialog and the chat refresh button (🔄) to invalidate cached profile avatars upon manual refresh.

### Sidebar Profile Picture Hydration
- Updated `quest_app/main.py` to automatically hydrate `avatar` from Firestore if not yet present in session state, ensuring the sidebar profile card always displays the active user's image.

### Login Page UI & Full-Bleed Layout
- Removed the empty black top bar by stripping Streamlit header heights and container padding across root DOM nodes (`.stApp`, `section.main`, `div[data-testid="stAppViewBlockContainer"]`, `div[data-testid="stMainBlockContainer"]`, `div[data-testid="stVerticalBlock"]`).
- Zeroed out default vertical container gap and hidden markdown/style element wrappers to ensure full-bleed `top: 0px` split-screen alignment.
- Restored clean field labels (`EMAIL`, `PASSWORD`) positioned directly above the input fields and properly centered the login container vertically.
- Restored the Benjamin Graham quote and styled the live index ticker chip at the top of the auth panel.

### Git & Remote Sync
- Synchronized commits across `origin/master` and `origin/main`.
- Resolved merge conflicts with remote commits cleanly.
- Renamed `Update Log/Tahir.md` to `Update Log/Thaheer.md`.

---

## 2026-08-27

### Routing & Session Navigation
- Fixed login and logout URL query parameter handling by removing stale `logged_out` parameter writes and ensuring clean `Overview` redirects.
- Added `just_logged_in` session-state synchronization across `login_page.py`, `quest_app/settings.py`, and `quest_app/main.py`.

### Chat System & Live Data
- Applied the missing Thaheer chat patch, linked received-message senders to their profiles, and removed duplicate portfolio snapshot code.
- Updated NSE live-data handling, including the NXST settlement price override.
- Consolidated planner, chat, and team update-log documentation.
