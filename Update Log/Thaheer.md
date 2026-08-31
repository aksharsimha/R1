# Thaheer Update Log

## 2026-08-31

### Knowledge Library & Games/Education Section (Mockup Matching)
- Created dedicated Knowledge Library page (`quest_app/tabs/education.py`) matching the design mockup.
- Connected the Library tab to the Games & Education sidebar workspace with custom XP status progress and environment switchers (`💼 Portfolio Dashboard` / `🏠 Switch to Hub`).
- Added top search bar with `⌘ K` keyboard shortcut badge, notification bell, and user profile avatar.
- Built 6 modern interactive educational cards with custom SVG artwork:
  1. *Glossary of Trading Terms* (BASICS, 8 min read)
  2. *The Power of Compounding* (INVESTING, 6 min read)
  3. *A Guide to Capital Gains Tax* (TAXES, 7 min read)
  4. *Support and Resistance Levels* (TRADING, 5 min read)
  5. *Build an Emergency Fund* (PERSONAL FINANCE, 6 min read)
  6. *Diversification Strategies* (ADVANCED STRATEGIES, 9 min read)
- Built interactive reading dialog (`@st.dialog`) with video lecture placeholder containers (ready for future video streams), full markdown study materials, and "Mark as Completed (+50 XP)" + "Bookmark" action buttons.
- Updated `edu_db.py` to persist bookmarks, completed modules, and XP rewards to Firestore.
- Added bottom pagination matching the design mockup (`Showing 1-6 of 128 articles` with pagination controls).

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