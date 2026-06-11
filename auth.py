"""
QUEST Authentication Module — Firebase Edition
================================================
Uses Firebase Auth for user registration/login and Firestore for profiles.
Passwords are managed by Firebase (bcrypt removed).

Features:
  - Register / Login with Firebase Auth (email + password)
  - Per-user data stored in Firestore (no local JSON files)
  - "Remember Me" via Streamlit session state
  - Password reset via Firebase email
"""

import os
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Paths (kept for backward compatibility with local Remember Me)
# ──────────────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(_HERE, "users")


def get_user_data_dir(username: str) -> str:
    """
    Return a placeholder path for backward compatibility.
    With Firebase, data lives in Firestore — not on disk.
    This is only used for legacy code paths.
    """
    user_dir = os.path.join(USERS_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


# ──────────────────────────────────────────────────────────────────────────────
# Registration (Firebase Auth + Firestore)
# ──────────────────────────────────────────────────────────────────────────────

def register_user(email: str, username: str, display_name: str, password: str) -> tuple[bool, str]:
    """
    Register a new user via Firebase.
    Returns (success: bool, message: str).
    """
    from firebase_db import create_user

    # Validation
    username = username.strip().lower()
    email = email.strip().lower()

    if not email:
        return False, "Email cannot be empty."
    if "@" not in email or "." not in email:
        return False, "Please enter a valid email."
    if not username:
        return False, "Username cannot be empty."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(username) > 30:
        return False, "Username must be 30 characters or fewer."
    if not all(c.isalnum() or c in ("_", "-", ".") for c in username):
        return False, "Username can only contain letters, numbers, underscores, hyphens, and dots."
    if not display_name.strip():
        return False, "Display name cannot be empty."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    ok, msg, _ = create_user(email, password, display_name.strip(), username)
    return ok, msg


# ──────────────────────────────────────────────────────────────────────────────
# Login (Firebase Auth REST API)
# ──────────────────────────────────────────────────────────────────────────────

def login_user(email: str, password: str) -> tuple[bool, str, dict | None]:
    """
    Authenticate via Firebase Auth.
    Returns (success: bool, message: str, user_info: dict | None).
    """
    from firebase_db import verify_login

    email = email.strip().lower()
    if not email or not password:
        return False, "Please enter both email and password.", None

    return verify_login(email, password)


# ──────────────────────────────────────────────────────────────────────────────
# Password Reset
# ──────────────────────────────────────────────────────────────────────────────

def reset_password(email: str) -> tuple[bool, str]:
    """Send password reset email via Firebase."""
    from firebase_db import send_password_reset
    return send_password_reset(email.strip().lower())


# ──────────────────────────────────────────────────────────────────────────────
# Remember Me — SESSION-ONLY (no server-side files)
# ──────────────────────────────────────────────────────────────────────────────
# Old bug: file-based remember-me on Streamlit Cloud was shared across ALL
# visitors, causing one user's login to auto-log in the next visitor.
# Fix: Remember Me now only works within the same Streamlit session.

def save_remember_me(username: str) -> None:
    """Remember Me is now handled by Streamlit session_state only."""
    # No file written — session_state already keeps the user logged in
    # for the duration of their browser session
    pass


def check_remember_me() -> dict | None:
    """No file-based remember me — always return None."""
    # Login is handled by session_state.authenticated + session_state.user_info
    return None


def clear_remember_me() -> None:
    """Nothing to clear — no files involved."""
    # Clean up any leftover .remember_me files from the old system
    remember_file = os.path.join(USERS_DIR, ".remember_me")
    if os.path.exists(remember_file):
        try:
            os.remove(remember_file)
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_user_display_name(username: str) -> str:
    """Get a user's display name from Firebase."""
    from firebase_db import get_user_display_name as fb_get_name
    return fb_get_name(username)


def user_exists(username: str) -> bool:
    """Check if a username is registered."""
    from firebase_db import user_exists as fb_exists
    return fb_exists(username)


def get_all_users() -> list[str]:
    """Return all registered usernames."""
    from firebase_db import get_all_users as fb_all
    return fb_all()
