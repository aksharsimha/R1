# Update Log - 2026-08-26 18:27:59 IST

### Authentication & Multi-Account Switching Fixes

1. **Sign-out Variable Scope Fix (quest_app/settings.py)**
   - Resolved a NameError crashing the app when clicking "Sign Out" by replacing an out-of-scope _user_info reference with the correct user_info parameter.

2. **Cookie Controller Preservation (quest_app/settings.py)**
   - Prevented the Streamlit cookie_controller from being destroyed during the session state wipe on sign-out. This ensures the multi-account cookie survives the sign-out process.

3. **Silent Cookie Write Failure Fixed (uth.py)**
   - Moved the uth_cookie_override session variable update *outside* of the 	ry/except block to prevent silent data loss.

4. **Ghost State Contamination Removed (login_page.py)**
   - Implemented a hard reset that scrubs old dashboard data before authenticating a new account, ensuring rigid boundaries between profiles.

5. **Manual Login Overrides Auto-Login (login_page.py)**
   - Actively submitting the login form now completely bypasses the background auto-login, preventing cookies from hijacking the login flow mid-process.

6. **Active Account Pinning (quest_app/main.py)**
   - Switching accounts now explicitly pins the selected account to the end of the cookie. Refreshing or opening a new tab keeps you in the correct account.

7. **Sign-Out Race Condition & Hijack Fix (login_page.py)**
   - Fixed a bug where do_logout was wiped instantly. It now persists securely until a new, successful login occurs, stopping the app from auto-logging into the wrong account while you type.
