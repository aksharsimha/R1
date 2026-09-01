# Thaheer Update Log

## 2026-08-26

### Git and deployment
- Pulled the latest changes from `origin/master`.
- Merged the remote updates into the local `master` branch.
- Relaunched the Streamlit app locally at `http://localhost:8501`.

### Application changes included
- Improved authentication and login-state handling to prevent stale or ghost
  session state from hijacking manual login and logout flows.
- Added and refined account settings, profile, security, and multi-account
  switching behavior.
- Added the `gfin.html` support page and related patch scripts from the latest
  remote update.
- Improved chat message sending, rendering, and notification behavior.
- Added Firebase support updates used by the chat and account flows.
- Updated dashboard routing and sidebar behavior.

### Latest working-tree updates
- Improved chat responsiveness with fragment-scoped reruns for chat actions,
  reducing unnecessary full-dashboard refreshes.
- Preserved chat scroll position across rerenders, automatically following new
  messages when the user is already near the latest message, and added explicit
  scroll-to-latest behavior after sending or sharing a message.
- Kept the chat input visible while the message list scrolls.
- Removed the Password & Security section from the Settings navigation and
  page rendering.
- Increased light-theme contrast for surfaces, borders, text, and accent states.
- Applied theme-aware colors to widget labels, inputs, radio buttons, checkboxes,
  and button icons for more consistent light and dark mode rendering.

### Files included in this push
- `auth.py`
- `chat_system.py`
- `firebase_db.py`
- `gfin.html`
- `login_page.py`
- `patch.py`
- `patch_chat.py`
- `patch_sender.py`
- `quest_app/main.py`
- `quest_app/settings.py`
- `quest_app/tabs/chat.py`
- `thaheer/README.md`

## 2026-08-27

### Planner and Gmail reminders
- Replaced the checkbox-only To-do list with a persistent productivity task
  manager.
- Added Pending, Completed, and Failed task states with an editable Status
  selector.
- Added task descriptions, priorities, due dates and times, categories,
  reminders, estimated time, recurrence choices, and subtasks.
- Added productivity totals, completion rate, progress bar, search, filters,
  sorting, overdue detection, duplicate, delete confirmation, and task
  reordering.
- Added migration for existing `{text, done}` task records.
- Added Gmail SMTP reminder delivery to the signed-in account email, including
  numeric reminders such as `1` for one minute before the due time.
- Added a Send test email action and retry behavior when delivery fails.

### Chat UI and presence
- Redesigned the chat area with a dark conversation rail, active conversation
  styling, avatar header, message bubbles, and responsive layout.
- Added functional conversation search, new conversation dialog, back
  navigation, profile/details actions, refresh, and portfolio sharing.
- Removed the layout spacer that caused a large empty area above the chat.
- Added Firestore `last_seen` heartbeats and real Online/Offline status based on
  recent activity.
- Restarted and verified the local Streamlit app at `http://localhost:8501`.

### Git updates
- Published the Planner, Gmail reminder, chat UI, and presence updates to the
  remote `main` branch.

## 2026-09-01

### ⚡ MICHAEL AI Video Study Assistant & Doubt Solver
- Integrated **MICHAEL AI Assistant** directly into the **Knowledge Library / Education Video Player** (`quest_app/tabs/education.py`).
- **Context-Aware Video Mentor**:
  - Automatically loads full context for whichever of the 200 videos the user is watching (Title, Creator, Module, Language, Summary, and Key Takeaways).
  - Clear user doubts on financial terminology (Demat, CAGR, Stop Loss, SEBI, P/E ratio, compounding, etc.) with real-world Indian stock market examples.
  - Supports both **English** and **Hindi/Hinglish** conversations seamlessly.
- **1-Click Quick Doubt Chips**:
  - `💡 Simple Summary`: Breaks down the lesson in plain, friendly concepts.
  - `📊 Indian Examples`: Explains real-world market applications with Nifty 50, BSE, and top equities.
- **Interactive Chat Interface & Whitespace Gap Elimination**:
  - Sleek dark glassmorphism card with user chat bubbles, timestamped answers, doubt input box, and doubt history reset.
  - Added `_format_ai_response_html()` parser to transform raw markdown tables into beautifully styled HTML tables with zero excess vertical padding.
  - Eliminated large empty black gaps by collapsing duplicate newlines and replacing raw `white-space: pre-wrap` with structured paragraph, header, and list item spacing.
  - Unified the video description & key takeaways container into a single structured HTML render block.
  - Powered by Groq / Gemini with an intelligent built-in pedagogical fallback engine.

---

### Main Hub Switchboard UI (Real Data Driven & Streamlined)
- Connected all Hub card metrics directly to real user data (`edu_db` & `portfolio_ledger`):
  - **Professional Portfolio**: Markets Tracked (live portfolio holdings count), Watchlist (live assets count), Alerts (live portfolio warnings count), and Last Updated (relative timestamp from latest transaction).
  - **Games & Education**: Total XP, Next XP milestone, Level number, Virtual Trading Balance, and Achievements / completed articles (`completed_articles / 100`).
- **Removed Motivation Strip**: Completely removed the bottom motivation card (quote, streak, weekly goal, and view achievements button) per user specifications.
- **Fixed HTML Formatting**: Cleared all leading whitespace from HTML strings in [`quest_app/tabs/hub.py`](file:///c:/Users/thahe/OneDrive/Documents/GitHub/R1/quest_app/tabs/hub.py) to prevent raw code block wrapping.

---

### Sidebar Environment Switcher & Page Refresh State Preservation
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
