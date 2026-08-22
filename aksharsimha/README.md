# Session: August 22, 2026
**Author:** Akshar Simha

## Goal
Fixing post-merge bugs related to the new authentication and routing structure.

## Changes Made
- **Dependency Update:** Installed the missing `streamlit-cookies-controller` which was added during the code split.
- **Fixed Render Crash (`auth.py`):** Patched a `NoneType` TypeError where the `CookieController` was crashing the Streamlit render loop by initializing multiple times. Cached the controller inside `st.session_state` to ensure it only initializes once per session.
- **Fixed Auto-Login Bug (`quest_app/main.py` & `login_page.py`):** Fixed a race condition on the "Sign Out" button. Previously, `st.rerun()` was firing so fast that it aborted the HTTP response before the browser could receive the JS command to delete the session cookie. Modified the routing so the cookie deletion happens during the login page render cycle, successfully wiping the keys.
