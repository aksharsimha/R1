# Thaheer Update Log

## 2026-09-01

### Sidebar Environment Switcher (Instant Tab Switching Without Logout)
- Added an **Environment Switcher** directly in the left sidebar (`💼 Portfolio` & `🎓 Education`).
- Enables 1-click seamless switching between **💼 Professional Portfolio** and **🎓 Games & Education** at any time without logging out or losing session state.
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