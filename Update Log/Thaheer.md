# Thaheer Update Log

## 2026-08-31

### YouTube-Style Video Learning Hub Overhaul (100 Curated Indian Financial Videos)
- Completely redesigned the Knowledge Library tab (`quest_app/tabs/education.py`) into a YouTube-style Video Learning Hub matching the user reference screenshot.
- Implemented responsive 16:9 cinema video player with real-time YouTube search resolving and video playback.
- Integrated complete 100-video Indian Financial Education catalog (`quest_app/education_catalog.json`) across all 10 pedagogical stages:
  - **Level 1 — First ₹1,000**: Zerodha Varsity, Pranjal Kamra, CA Rachana Ranade, Groww, Warikoo, Asset Yogi, Akshat Shrivastava, SEBI Investor Education.
  - **Level 2 — Grow Your Money**: Compounding math, SIP vs Lumpsum, inflation, Rule of 72, emergency funds.
  - **Level 3 — Reach Your Goal**: Goal-based financial planning, time horizons, retirement planning at 25 vs 35.
  - **Level 4 — What's Your Style?**: Risk profiling, active vs passive, value vs growth, behavioural biases.
  - **Level 5 — Build Your Portfolio**: Asset allocation, equity/debt/gold mix, portfolio rebalancing, large/mid/small caps.
  - **Level 6 — What Happens If...?**: Market crashes, term & health insurance, stop losses, hedging with options.
  - **Level 7 — News Detective**: Reading business news, RBI monetary policy, US Fed impact, quarterly earnings seasons.
  - **Level 8 — Read the Market**: Technical analysis, candlestick charts, support & resistance, balance sheets, P/E & ROE.
  - **Level 9 — Market Storm**: 2008 Crisis, Covid 2020 crash, VIX fear index, Harshad Mehta 1992 scam, circuit breakers.
  - **Standalone — Tax Detective**: STCG vs LTCG on equities, ITR filing for traders, Old vs New tax regime, Section 80C, ELSS.
- Creator Bar: Added channel avatars, verified badges (`✔`), subscriber counts, and interactive `+ Follow` buttons.
- Quick Actions: Built interactive `👍 Likes`, `🔖 Save / Bookmark`, `↗ Share`, and `🎓 Mark as Watched (+50 XP)` controls.
- Resources & Notes: Added downloadable PDF cheatsheets (`.pdf • 1.2 MB`) and direct "Open in YouTube ↗" links.
- "Up Next" Playlist: Built interactive playlist sidebar with level filtering, duration badges, view counts, and instant 1-click video switching.

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