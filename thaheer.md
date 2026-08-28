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

## 2026-08-28

### News AI Dashboard & Full Interactivity Overhaul
- Redesigned the News tab (`quest_app/tabs/news.py`) into the modern News AI Dashboard matching the user mockup.
- Swapped two-column layout so Latest News is placed on the Left and Market Overview on the Right.
- Removed top sentiment KPI metric cards and sentiment summary bar to streamline header and eliminate clutter.
- Built Market Overview panel with live NIFTY 50 and SENSEX metrics, sparklines, and market breadth (Advances / Declines / Unchanged).
- Added **🔥 Trending Market Topics** section with interactive market theme pills (`#NIFTY25K`, `#Q2Results`, `#RBIPolicy`, `#AITechRally`, etc.).
- Added **📅 Earnings & Dividends Calendar** integrated with Yahoo Finance to display upcoming quarter results release dates, consensus EPS estimates, and dividend ex-dates for user holdings and Indian market leaders.
- Built Latest News feed with live market articles from NSE benchmarks, category tags, thumbnails, read times, and `View All News →` modal.
- Removed notification icon from top header and preserved Search 🔍 and Profile 👤 quick actions.
- Built 10-Year Historical News & Sentiment Archive (2016-2026) 📁 with multi-year filter, era milestone shortcuts, and keyword/ticker search.

### Chat Avatars & Profile Pictures
- Replaced letter placeholders with actual user profile avatars across the Chat tab (`quest_app/tabs/chat.py`).
- Added cached profile and avatar rendering helpers (`_get_profile_cached`, `_render_avatar_html`) to load avatars from Firestore.
- Updated the Chat header to show the other participant's avatar image alongside a live status badge (`.chat-avatar-wrap`).
- Added avatar thumbnails to both received messages (left side) and sent messages (right side) in the message stream.
- Updated the Public Profile dialog and the chat refresh button (🔄) to invalidate cached profile avatars upon manual refresh.

### Sidebar Profile Picture Hydration
- Updated `quest_app/main.py` to automatically hydrate `avatar` from Firestore if not yet present in session state, ensuring the sidebar profile card always displays the active user's image.

### Git & Remote Sync
- Synchronized commits across `origin/master` and `origin/main`.
- Resolved merge conflicts with remote commits cleanly.
- Renamed `Update Log/Tahir.md` to `Update Log/Thaheer.md`.
