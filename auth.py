"""
QUEST Authentication Module
============================
Handles user registration, login, session management, and per-user data
directory creation. Passwords are hashed with bcrypt. Each user gets an
isolated data directory under users/<username>/.

Features:
  - Register / Login with bcrypt-hashed passwords
  - Per-user data directory (holdings, predictions, transactions, EWMA, news)
  - "Remember Me" via a local token file
  - Auto-migration of legacy root-level data to the first registered user
"""

import json
import os
import shutil
import secrets
from datetime import datetime

import bcrypt

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(_HERE, "users")
USERS_DB_FILE = os.path.join(USERS_DIR, "users.json")
REMEMBER_ME_FILE = os.path.join(USERS_DIR, ".remember_me")

# Data files that each user gets their own copy of
USER_DATA_FILES = [
    "holdings.json",
    "transactions_log.json",
    "predictions_log.json",
    "adaptive_state.json",
    "news_archive.json",
]

# ──────────────────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_users_dir():
    """Create users/ directory if it doesn't exist."""
    os.makedirs(USERS_DIR, exist_ok=True)


def _load_db() -> dict:
    """Load the users database from disk."""
    _ensure_users_dir()
    if not os.path.exists(USERS_DB_FILE):
        return {"users": {}}
    try:
        with open(USERS_DB_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"users": {}}


def _save_db(db: dict) -> None:
    """Atomically save the users database."""
    _ensure_users_dir()
    tmp = USERS_DB_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp, USERS_DB_FILE)


# ──────────────────────────────────────────────────────────────────────────────
# User data directory
# ──────────────────────────────────────────────────────────────────────────────

def get_user_data_dir(username: str) -> str:
    """Return the absolute path to a user's data directory."""
    return os.path.join(USERS_DIR, username)


def _create_user_data_dir(username: str) -> str:
    """Create a user's data directory with default files if needed."""
    user_dir = get_user_data_dir(username)
    os.makedirs(user_dir, exist_ok=True)

    # Create a default holdings.json if none exists
    holdings_path = os.path.join(user_dir, "holdings.json")
    if not os.path.exists(holdings_path):
        with open(holdings_path, "w") as f:
            json.dump({"holdings": []}, f, indent=2)

    return user_dir


def migrate_legacy_data(username: str) -> bool:
    """
    Migrate legacy root-level data files to a user's directory.
    This is for the first user (akshar) who has existing data in the project root.
    Only copies files that exist in root AND don't already exist in user dir.
    Returns True if any files were migrated.
    """
    user_dir = get_user_data_dir(username)
    os.makedirs(user_dir, exist_ok=True)
    migrated = False

    for filename in USER_DATA_FILES:
        src = os.path.join(_HERE, filename)
        dst = os.path.join(user_dir, filename)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            migrated = True

    return migrated


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

def register_user(username: str, display_name: str, password: str) -> tuple[bool, str]:
    """
    Register a new user.

    Returns (success: bool, message: str).
    """
    # Validation
    username = username.strip().lower()
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

    db = _load_db()

    if username in db["users"]:
        return False, "Username already taken."

    # Hash password with bcrypt
    salt = bcrypt.gensalt(rounds=12)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    db["users"][username] = {
        "display_name": display_name.strip(),
        "password_hash": password_hash,
        "created_at": datetime.now().isoformat(),
        "last_login": datetime.now().isoformat(),
    }

    _save_db(db)

    # Create user data directory
    _create_user_data_dir(username)

    return True, "Account created successfully!"


# ──────────────────────────────────────────────────────────────────────────────
# Login
# ──────────────────────────────────────────────────────────────────────────────

def login_user(username: str, password: str) -> tuple[bool, str, dict | None]:
    """
    Authenticate a user.

    Returns (success: bool, message: str, user_info: dict | None).
    user_info contains: username, display_name, data_dir
    """
    username = username.strip().lower()
    if not username or not password:
        return False, "Please enter both username and password.", None

    db = _load_db()

    if username not in db["users"]:
        return False, "Invalid username or password.", None

    user = db["users"][username]
    stored_hash = user["password_hash"].encode("utf-8")

    if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
        return False, "Invalid username or password.", None

    # Update last login
    db["users"][username]["last_login"] = datetime.now().isoformat()
    _save_db(db)

    # Ensure data directory exists
    user_dir = _create_user_data_dir(username)

    return True, f"Welcome back, {user['display_name']}!", {
        "username": username,
        "display_name": user["display_name"],
        "data_dir": user_dir,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Remember Me
# ──────────────────────────────────────────────────────────────────────────────

def save_remember_me(username: str) -> None:
    """Save a remember-me token for auto-login."""
    _ensure_users_dir()
    token = secrets.token_hex(32)

    db = _load_db()
    if username in db["users"]:
        db["users"][username]["remember_token"] = token
        _save_db(db)

    with open(REMEMBER_ME_FILE, "w") as f:
        json.dump({"username": username, "token": token}, f)


def check_remember_me() -> dict | None:
    """
    Check if a valid remember-me token exists.
    Returns user_info dict if valid, None otherwise.
    """
    if not os.path.exists(REMEMBER_ME_FILE):
        return None

    try:
        with open(REMEMBER_ME_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        clear_remember_me()
        return None

    username = data.get("username", "")
    token = data.get("token", "")

    if not username or not token:
        clear_remember_me()
        return None

    db = _load_db()
    user = db["users"].get(username)
    if not user:
        clear_remember_me()
        return None

    if user.get("remember_token") != token:
        clear_remember_me()
        return None

    # Valid token — auto-login
    user_dir = _create_user_data_dir(username)
    return {
        "username": username,
        "display_name": user["display_name"],
        "data_dir": user_dir,
    }


def clear_remember_me() -> None:
    """Remove the remember-me token file."""
    if os.path.exists(REMEMBER_ME_FILE):
        try:
            os.remove(REMEMBER_ME_FILE)
        except OSError:
            pass

    # Also clear token from DB
    db = _load_db()
    for user in db["users"].values():
        user.pop("remember_token", None)
    _save_db(db)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_user_display_name(username: str) -> str:
    """Get a user's display name."""
    db = _load_db()
    user = db["users"].get(username, {})
    return user.get("display_name", username)


def user_exists(username: str) -> bool:
    """Check if a username is already registered."""
    db = _load_db()
    return username.strip().lower() in db["users"]


def get_all_users() -> list[str]:
    """Return a list of all registered usernames."""
    db = _load_db()
    return list(db["users"].keys())
