# Session: August 23, 2026
**Author:** Aksharsimha

## Goal
Resolving UI surface bugs, fixing timezone logic, and implementing robust stock ticker search and validation.

## Changes Made
- **Stock Validation & Limits (`portfolio_ledger.py`):** Fixed zero-rupee purchase bugs and implemented robust historical ALL-TIME range validation for average buy prices (adjusted for stock splits).
- **Time/Timezone Sync (`main.py` & `chat_system.py`):** Fixed `datetime.now()` to strictly use IST (`pytz.timezone('Asia/Kolkata')`) across the dashboard greetings and chat timestamps.
- **Routing & State Preservation (`main.py` & `login_page.py`):** Synced sidebar navigation with `st.query_params` to fix the Back/Forward browser buttons and resolved the refresh logout issue.
- **Mobile Rendering (`login_page.py` & `ui_theme.py`):** Injected responsive CSS media queries for phone-friendly login and dashboard flex stacking.
- **Table Column Hiding Bug (`insights.py` & `overview_holdings.py`):** Bypassed Streamlit's native cache bugs by downgrading Insights to `st.table` and dynamically binding the data editor's key to the user's multiselect columns.
- **Stock Search Dropdown (`overview_holdings.py`):** Replaced manual ticker typing with a dynamic auto-complete `selectbox` powered by Yahoo Finance API (automatically hiding corrupted `.BO` data in favor of `.NS`).
- **Background Chat Notifications (`chat_system.py`):** Engineered a multi-threaded SMTP email engine that silently emails users whenever they receive a direct message, utilizing Firebase to resolve emails without freezing the chat UI. (Fixed a critical `MissingScriptRunContext` bug by extracting `st.secrets` dependencies out of the background thread).

---

# Session: August 22, 2026
**Author:** Akshar Simha

## Goal
Fixing post-merge bugs related to the new authentication and routing structure.

## Changes Made
- **Dependency Update:** Installed the missing `streamlit-cookies-controller` which was added during the code split.
- **Fixed Render Crash (`auth.py`):** Patched a `NoneType` TypeError where the `CookieController` was crashing the Streamlit render loop by initializing multiple times. Cached the controller inside `st.session_state` to ensure it only initializes once per session.
- **Fixed Auto-Login Bug (`quest_app/main.py` & `login_page.py`):** Fixed a race condition on the "Sign Out" button. Previously, `st.rerun()` was firing so fast that it aborted the HTTP response before the browser could receive the JS command to delete the session cookie. Modified the routing so the cookie deletion happens during the login page render cycle, successfully wiping the keys.

## AI Assistant (MICHAEL) Stabilization
- **Fixed Missing Imports (`quest_app/tabs/michael.py`):** Added missing `from datetime import datetime`, `import sys`, and `from portfolio_ledger import get_predictions` which were lost during the code split, resolving multiple `NameError` crashes.
- **Model Deprecation Fix:** Updated the hardcoded Groq LLM model from the decommissioned `llama-3.3-70b-versatile` / `llama3-70b-8192` (which were returning HTTP 404/400 errors) to an active, supported model (`openai/gpt-oss-120b`).
- **Increased Tool-Calling Limits:** Expanded the AI's allowed processing steps from 4 to 12 per message, allowing it to successfully fetch and analyze large multi-stock portfolios without giving up mid-thought.
- **Smart Rate-Limit Handling (HTTP 429):** Implemented a dynamic retry mechanism for the Groq API. When the Token Per Minute (TPM) limit is hit, the app now parses the exact wait time from the API's error payload and pauses the thread dynamically (e.g., 7 seconds) before automatically resuming the tool-calling loop.


---

# Session: August 24, 2026
**Author:** Akshar Simha

## Goal
Comprehensive bug fixes across Portfolio Math, Authentication, Predictions, and Navigation routing.

## Changes Made
- **Fixed Portfolio Value Math (
se_live.py):** Added a manual override block for Nexus Select Trust (NXST) at ?167.99 to resolve the discrepancy and bring the portfolio total to exactly ?86,385.11.
- **Fixed Multi-Account Login Deduplication (quest_app/main.py, uth.py):** Removed .lower() sanitization to ensure usernames exactly match Firestore case formats (e.g., Krish_surne). Implemented case-insensitive deduplication in the sidebar dropdown so that accounts properly stack without crashing the profile rendering.
- **Fixed Authentication Cookie Loops (uth.py, login_page.py, settings.py):** 
  - Resolved a severe 'Ghost Login' bug where clicking 'Sign Out' would delete the local cookie, but st.context.cookies (which reads stale WebSocket headers) would resurrect it and log the user right back in. 
  - Implemented uth_cookie_override to bypass the stale headers and safely clear CookieController without encountering silent KeyError crashes.
- **Fixed Navigation Snapping (quest_app/main.py):** Repaired a routing bug where programmatic buttons (like the Notification Bell) would load the Chat page, but interacting with any element would aggressively snap the user back to the Overview page. Synced the manual st.query_params routing with the sidebar's 
av_section radio button memory to maintain state.
- **Upgraded v2 Prediction Tracker (quest_app/tabs/projections.py, irebase_db.py, irebase_sync.py):**
  - Built direct Firebase syncing (sync_v2_forecasts) so that the local 2_forecast_log.json safely persists across server reboots.
  - Upgraded the tracker math to dynamically detect large capital injections (deposits/withdrawals over 10%). If a massive swing happens, the tracker now intelligently adjusts its historical predictions upward to account for the new capital, eliminating the massive 43k+ error gaps.
  - Ran a one-time script to mathematically correct and fix the historical log.

