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
