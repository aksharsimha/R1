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

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime

import streamlit as st
from streamlit_cookies_controller import CookieController

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
# Remember Me — signed browser cookie
# ──────────────────────────────────────────────────────────────────────────────
_REMEMBER_COOKIE = "quest_remember"
_REMEMBER_DAYS = 30


def _remember_secret() -> bytes:
    """Load the server-only secret used to sign remember-me cookies."""
    secret = os.environ.get("QUEST_REMEMBER_SECRET")
    if not secret:
        secret_path = os.path.join(_HERE, ".streamlit", "remember_secret.txt")
        try:
            with open(secret_path, encoding="utf-8") as handle:
                secret = handle.read().strip()
        except OSError:
            secret = secrets.token_urlsafe(32)
            try:
                os.makedirs(os.path.dirname(secret_path), exist_ok=True)
                with open(secret_path, "x", encoding="utf-8") as handle:
                    handle.write(secret)
            except FileExistsError:
                with open(secret_path, encoding="utf-8") as handle:
                    secret = handle.read().strip()
    return secret.encode("utf-8")


def _cookies() -> CookieController:
    if "cookie_controller" not in st.session_state:
        st.session_state.cookie_controller = CookieController(key="quest_auth_cookies")
    return st.session_state.cookie_controller

def _remembered_cookie() -> list[dict]:
    """Read the multi-account cookie, migrating the legacy single token."""
    token = st.context.cookies.get(_REMEMBER_COOKIE)
    if not token:
        token = _cookies().get(_REMEMBER_COOKIE)
    if not token:
        return []
    
    import urllib.parse
    token_str = urllib.parse.unquote(str(token))

    try:
        entries = json.loads(token_str)
        if isinstance(entries, dict):
            entries = [entries]
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    except (TypeError, json.JSONDecodeError):
        pass
    # Legacy format: base64(username).hmac.
    if "." in token_str:
        payload, signature = token_str.split(".", 1)
        username = _decode_signed_username(payload, signature)
        if username:
            return [{"username": username, "display_name": username,
                     "signed_token": token_str, "_legacy": True}]
    return []


def _decode_signed_username(payload: str, signature: str) -> str | None:
    expected = hmac.new(_remember_secret(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
    except Exception:
        return None


def _write_remembered_cookie(entries: list[dict]) -> None:
    _cookies().set(
        _REMEMBER_COOKIE,
        json.dumps(entries, separators=(",", ":")),
        max_age=_REMEMBER_DAYS * 24 * 60 * 60,
        same_site="lax",
    )


def add_remembered_account(username: str, display_name: str | None = None) -> None:
    """Append a signed account entry, replacing any existing entry for it."""
    username = username.strip()
    payload = base64.urlsafe_b64encode(username.encode()).decode().rstrip("=")
    signature = hmac.new(_remember_secret(), payload.encode(), hashlib.sha256).hexdigest()
    entries = [entry for entry in _remembered_cookie() if entry.get("username") != username]
    entries.append({"username": username, "display_name": display_name or username,
                    "signed_token": f"{payload}.{signature}"})
    _write_remembered_cookie(entries)


def save_remember_me(username: str) -> None:
    """Backward-compatible alias that adds the account to remembered accounts."""
    add_remembered_account(username)


def get_remembered_accounts() -> list[dict]:
    """Return valid remembered accounts and drop forged or malformed entries."""
    valid = []
    changed = False
    for entry in _remembered_cookie():
        token = str(entry.get("signed_token", ""))
        if "." not in token:
            changed = True
            continue
        payload, signature = token.split(".", 1)
        username = _decode_signed_username(payload, signature)
        if not username or username != str(entry.get("username", "")).strip():
            changed = True
            continue
        valid.append({"username": username, "display_name": entry.get("display_name") or username,
                      "signed_token": token})
        changed = changed or bool(entry.get("_legacy"))
    if changed:
        _write_remembered_cookie(valid)
    return [{"username": entry["username"], "display_name": entry["display_name"]}
            for entry in valid]


def remove_remembered_account(username: str) -> None:
    """Forget one account without affecting the other remembered accounts."""
    username = username.strip()
    entries = [entry for entry in _remembered_cookie() if entry.get("username") != username]
    if entries:
        _write_remembered_cookie(entries)
    else:
        clear_remember_me()


def check_remember_me() -> dict | None:
    """Restore the most recently added valid remembered account."""
    accounts = get_remembered_accounts()
    return accounts[-1] if accounts else None


def clear_remember_me() -> None:
    """Remove the browser cookie and any legacy local marker."""
    try:
        ctrl = _cookies()
        # Set to empty first to avoid KeyError if the controller was just initialized
        ctrl.set(_REMEMBER_COOKIE, "[]")
        ctrl.remove(_REMEMBER_COOKIE)
    except Exception:
        pass
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
