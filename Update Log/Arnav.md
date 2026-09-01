# Arnav

# Session: August 23, 2026
**Author:** Arnav

## Goal
Redesign the QUEST dashboard sidebar and account settings experience, then add secure multi-account switching for accounts remembered on the current device.

## Changes Made
- **Dashboard Sidebar (`quest_app/main.py` & `ui_theme.py`):** Added the profile block with avatar, display name, username, and account selector; restored all dashboard destinations including Overview, Planner, Analytics, Projections, Insights, News, Activity, Chat, and MICHAEL.
- **Sidebar Actions (`quest_app/main.py`):** Added functional Settings and notification buttons beside the profile area. The Settings button opens the Settings page and the notification button routes to the Chat tab.
- **Sidebar Toggle (`quest_app/main.py` & `ui_theme.py`):** Hid Streamlit's native collapse arrow and added a vertical three-bar hamburger button that triggers the native sidebar collapse behavior.
- **Settings Page (`quest_app/settings.py`):** Added a dedicated native Settings sidebar with Dashboard, Profile, Theme, Password & Security, and Sign out sections. The Dashboard button returns to the main Overview page.
- **Profile Settings (`quest_app/settings.py` & `firebase_db.py`):** Added avatar upload, avatar deletion, editable display name, and editable profile summary support.
- **Theme Settings (`quest_app/settings.py`):** Added Light and Dark theme controls. Removed the separate theme switch and Sign Out button from the main dashboard so they are available through Settings.
- **Password & Security (`quest_app/settings.py` & `firebase_db.py`):** Added password changes, password-protected email updates with Firebase verification email delivery, and password-protected phone number updates. Email and username changes retain the 24-hour cooldown behavior.
- **Firebase Profile Operations (`firebase_db.py`):** Added profile retrieval and update helpers, avatar persistence, password verification, email verification, phone updates, and username migration while preserving existing Firebase data.
- **Multi-Account Remember Me (`auth.py`):** Replaced the single remembered-account cookie with a signed JSON list of accounts, added legacy cookie migration, signature validation, account addition, and account removal helpers.
- **Account Switcher (`quest_app/main.py` & `login_page.py`):** Replaced the unsafe Firebase-wide user list with only valid accounts remembered on the current device. Added `+ Add account`, password-free switching for signed remembered accounts, fresh Firebase data hydration after switching, and normal login persistence for newly added accounts.
- **Authentication Safety (`auth.py` & `quest_app/main.py`):** Ensured dashboard reruns do not overwrite remembered account metadata and that forged or malformed remembered-cookie entries are discarded.

## Validation
- Python compilation and VS Code diagnostics passed for all edited modules.
- The running Streamlit app responded successfully on `http://localhost:8501`.

---

# Session: August 23, 2026 — Sidebar Bug Fixes
**Author:** Arnav

## Goal
Fix two persistent sidebar bugs: (1) nav items not stretching to the full sidebar width, and (2) the settings gear and notification bell reopening the app in a new tab and dropping the user back on the login page.

## Changes Made
- **Sidebar nav width (`ui_theme.py`):** Traced the full Streamlit DOM chain — `stSidebarContent → stVerticalBlock → stMarkdownContainer → stRadio → [role="radiogroup"] → label` — and applied `width: 100% !important; box-sizing: border-box !important` at every node in the chain. Added `stMarkdownContainer`, `stRadio`, `stWidgetLabel`, and `stElementContainer` to the blanket sidebar width selector. Also added `display: flex; flex-direction: column` to the radiogroup container so labels fill it edge-to-edge, matching the profile card and account switcher above them at every sidebar width.
- **Icon button row CSS (`ui_theme.py`):** Added `.quest-icon-btn-row` and its child selectors to style the real `st.button()` wrappers as icon tiles with identical hover behaviour to the old anchors, while stripping Streamlit's default column padding so they share the same left/right edges as all other sidebar elements.
- **Settings and bell navigation (`quest_app/main.py`):** Removed the raw `<a href="?page=Settings">` and `<a href="?page=Chat">` HTML anchors that were causing full browser navigation (session loss → login redirect). Replaced with two real `st.button()` calls inside `st.sidebar.columns(2)`. Each button sets `st.query_params["page"]` and calls `st.rerun()` to navigate within the same session — no page reload, no login redirect.

## Validation
- `grep` confirmed zero remaining `href="?page=` anchors in `main.py`.
- `st.button` keys `sidebar_settings_btn` and `sidebar_chat_btn` confirmed present at lines 136 and 141.
- Streamlit app restarted cleanly on `http://localhost:8501` with no import or runtime errors.

## [2026-08-24] — Fix: Login always lands on Settings instead of Overview

### Fixed
- **Post-login navigation reset**: After logging out and back in (any
  account — manual login, remembered account, new signup, or live demo),
  the app was landing on the Settings page instead of Overview. Added
  `st.query_params["page"] = "Overview"` and
  `st.query_params.pop("return_to", None)` right before each `st.rerun()`
  in `login_page.py`'s login/signup/demo success paths, so navigation
  correctly resets to Overview on every fresh authentication.

---

# Session: August 27, 2026 — Fix Signout/Signin Redirect Race Condition
**Author:** Arnav

## Goal
Resolve the issue where signing out from the settings page and signing back in redirected users (especially other developers or in incognito mode) back to the Settings page instead of the Overview page.

## Changes Made
- **Early Page Routing (`quest_app/main.py`):** Added a check for a `just_logged_in` session state flag. If present, the routing forces the page to `"Overview"` and clears the flag. This acts as a robust server-side override to bypass browser-side query parameter race conditions.
- **Login success paths (`login_page.py`):** Updated all login paths (auto-login, manual login, live demo, signup, and add-account screen) to set `st.session_state.just_logged_in = True` on successful authentication. Cleaned up duplicate assignments of `st.query_params["page"] = "Overview"`.
- **Sign-Out Transition (`quest_app/settings.py`):** Updated the "Sign out" button to reset the `page` query parameter to `"Overview"` and pop `return_to` immediately upon sign-out. This clears the settings URL parameter early, allowing the browser plenty of time to process the URL update before the user logs back in.

## Validation
- Verified that local changes merge cleanly with the new "Soft Sign-Out" feature pulled from upstream.
- Successfully committed the changes locally.

Here's a condensed version:

---

## [2026-08-28] Performance Overhaul: Faster Loads, Smarter Caching

**Root cause:** Streamlit reran the entire script on every interaction, triggering live price fetches, news calls, risk computations, and file reads each time.

---

**Fix 1: Portfolio analysis cached for 30s** (`main.py`)
Heavy lifting (price fetch, volatility, PCA, risk scores) now runs once per 30s cycle. Button clicks and tab switches are instant on cache hits. Editing a holding immediately invalidates the cache.

**Fix 2: News sentiment parallelized + cached** (`news_sentiment.py`, `main.py`)
All stocks fetch simultaneously instead of sequentially. Results cached per stock for 5 minutes.
- Before: 8 stocks x ~5s = ~40s cold load
- After: ~5s cold, ~0s warm

**Fix 3: EWMA and prediction grading run only when needed** (`main.py`)
`ewma_catchup` and `evaluate_past_predictions` are now tied to the 30s analysis cycle instead of firing on every widget interaction.

**Fix 4: Debug timing panel** (`main.py`)
Append `?debug=1` to the URL to reveal per-block timing. Temporary, invisible otherwise.

---

| What | Before | After |
|---|---|---|streamlit run quest_app/main.py
| Portfolio analysis | ~5-15s per click | Cached 30s, instant on hit |
| News fetching | ~40s cold, sequential | ~5s cold, 0s warm, parallel |
| EWMA / grading | Every interaction | Every 30s cycle |
| Portfolio edits | Delayed up to 30s | Immediate (cache cleared) |

No UI or calculation changes.

---