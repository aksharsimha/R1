"""
QUEST Firebase Database Layer
==============================
Single abstraction layer for all Firestore operations.
Every module (auth, portfolio_ledger, chat_system, adaptive_engine)
calls this instead of reading/writing JSON files.

Setup:
  1. Place Firebase service account key at .streamlit/firebase_key.json
  2. Or set Streamlit secrets (for cloud deployment)
"""

import json
import os
import threading
from datetime import datetime, timezone
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

# ──────────────────────────────────────────────────────────────────────────────
# Initialization
# ──────────────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_db = None
_init_lock = threading.Lock()


def init_firebase():
    """Initialize Firebase Admin SDK. Safe to call multiple times."""
    global _db

    if _db is not None:
        return _db

    # Streamlit can run this function concurrently during reruns or new sessions.
    with _init_lock:
        if _db is not None:
            return _db

        # Reuse the default app if another module initialized it first.
        try:
            app = firebase_admin.get_app()
        except ValueError:
            app = None

        if app is None:
            # Try .streamlit/firebase_key.json first (local dev)
            key_path = os.path.join(_HERE, ".streamlit", "firebase_key.json")
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
                app = firebase_admin.initialize_app(cred)
            else:
                # Try Streamlit secrets (cloud deployment)
                try:
                    key_dict = dict(st.secrets["firebase"])
                    # Fix escaped newlines if user copy-pasted the raw string from JSON
                    if "private_key" in key_dict:
                        key_dict["private_key"] = key_dict["private_key"].replace('\\n', '\n')
                    cred = credentials.Certificate(key_dict)
                    app = firebase_admin.initialize_app(cred)
                except Exception:
                    app = None

        if app is not None:
            _db = firestore.client(app)
            return _db

    raise RuntimeError(
        "Firebase key not found. Place firebase_key.json in .streamlit/ "
        "or configure Streamlit secrets."
    )


def get_db():
    """Get Firestore client, initializing if needed."""
    global _db
    if _db is None:
        init_firebase()
    return _db


# ──────────────────────────────────────────────────────────────────────────────
# Auth — User Management
# ──────────────────────────────────────────────────────────────────────────────

def create_user(email: str, password: str, display_name: str, username: str) -> tuple[bool, str, dict | None]:
    """
    Create a new user via Firebase Auth + Firestore profile.
    Returns (success, message, user_info).
    """
    db = get_db()

    # Check if username is taken in Firestore
    user_doc = db.collection("users").document(username).get()
    if user_doc.exists:
        return False, "Username already taken.", None

    try:
        # Create Firebase Auth user
        fb_user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
        )
    except firebase_auth.EmailAlreadyExistsError:
        return False, "Email already registered.", None
    except Exception as e:
        return False, f"Registration failed: {str(e)}", None

    # Create Firestore user profile
    profile = {
        "uid": fb_user.uid,
        "email": email,
        "display_name": display_name,
        "username": username,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    db.collection("users").document(username).set(profile)

    # Create email→username mapping for login lookup
    db.collection("email_to_username").document(email).set({
        "username": username,
    })

    # Initialize empty portfolio
    db.collection("users").document(username).collection("data").document("holdings").set({
        "holdings": [],
    })

    user_info = {
        "username": username,
        "display_name": display_name,
        "uid": fb_user.uid,
        "email": email,
    }
    return True, "Account created successfully!", user_info


def verify_login(email: str, password: str) -> tuple[bool, str, dict | None]:
    """
    Verify login credentials.
    Firebase Admin SDK doesn't support password verification directly,
    so we use the Firebase Auth REST API.
    Returns (success, message, user_info).
    """
    import requests

    db = get_db()

    # Get the Firebase project's Web API key
    # We need to read it from the firebase key file
    api_key = _get_web_api_key()
    if not api_key:
        return False, "Firebase API key not configured.", None

    # Use Firebase Auth REST API to verify password
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
    except Exception as e:
        return False, f"Login failed: {str(e)}", None

    if resp.status_code != 200:
        error_msg = data.get("error", {}).get("message", "Invalid credentials")
        if "INVALID_LOGIN_CREDENTIALS" in error_msg or "EMAIL_NOT_FOUND" in error_msg:
            return False, "Invalid email or password.", None
        return False, f"Login failed: {error_msg}", None

    # Get username from email mapping
    try:
        email_doc = db.collection("email_to_username").document(email).get()
    except Exception as e:
        return False, f"Login failed: {str(e)}", None
    if not email_doc.exists:
        return False, "Account not found. Please sign up.", None

    username = email_doc.to_dict().get("username", "").strip()
    if not username:
        return False, "Account data corrupted. Please contact support.", None

    # Get full profile
    profile_doc = db.collection("users").document(username).get()
    if not profile_doc.exists:
        return False, "Profile not found.", None

    profile = profile_doc.to_dict()

    user_info = {
        "username": username,
        "display_name": profile.get("display_name", username),
        "uid": profile.get("uid", ""),
        "email": email,
    }
    # Include avatar so the sidebar profile card shows it immediately
    if profile.get("avatar"):
        user_info["avatar"] = profile["avatar"]
    return True, f"Welcome back, {user_info['display_name']}!", user_info


def _get_web_api_key() -> str | None:
    """Get Firebase Web API key from Streamlit secrets or env."""
    # First check streamlit secrets (only return if actually present —
    # st.secrets.get() returns None when absent, which must NOT short-circuit
    # the env/file fallbacks below).
    try:
        _v = st.secrets.get("firebase_web_api_key", None)
        if _v:
            return _v
    except Exception:
        pass

    # Check environment variable
    key = os.environ.get("FIREBASE_WEB_API_KEY")
    if key:
        return key

    # Try to read from a config file
    config_path = os.path.join(_HERE, ".streamlit", "firebase_web_api_key.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return f.read().strip()

    return None


def user_exists(username: str) -> bool:
    """Check if a username exists in Firestore."""
    db = get_db()
    return db.collection("users").document(username).get().exists


def get_user_display_name(username: str) -> str:
    """Get display name from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).get()
    if doc.exists:
        return doc.to_dict().get("display_name", username)
    return username


def get_user_profile(username: str) -> dict:
    """Read a complete user profile, returning useful defaults when absent."""
    if not username or not username.strip():
        return {"username": "", "display_name": ""}
    db = get_db()
    doc = db.collection("users").document(username).get()
    return doc.to_dict() if doc.exists else {"username": username, "display_name": username}


def set_user_presence(username: str) -> bool:
    """Record the latest heartbeat for a signed-in user."""
    if not username or not get_db():
        return False
    try:
        get_db().collection("users").document(username).update({
            "last_seen": datetime.now(timezone.utc),
        })
        return True
    except Exception:
        return False


def is_user_online(username: str, timeout_seconds: int = 90) -> bool:
    """Return whether a user's last heartbeat is within the active window."""
    profile = get_user_profile(username)
    last_seen = profile.get("last_seen")
    if not last_seen:
        return False
    try:
        if isinstance(last_seen, str):
            last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last_seen).total_seconds() <= timeout_seconds
    except (TypeError, ValueError):
        return False


def _password_token(email: str, password: str) -> str | None:
    """Verify a password and return a short-lived Firebase ID token."""
    import requests

    api_key = _get_web_api_key()
    if not api_key:
        return None
    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
        json={"email": email, "password": password, "returnSecureToken": False},
        timeout=10,
    )
    return response.json().get("idToken") if response.status_code == 200 else None


def _within_profile_cooldown(profile: dict, field: str) -> bool:
    value = profile.get(field)
    if not value:
        return False
    if hasattr(value, "timestamp"):
        value = datetime.fromtimestamp(value.timestamp(), tz=timezone.utc)
    elif isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - value).total_seconds() < 86400


def update_display_name(username: str, display_name: str) -> tuple[bool, str]:
    """Update the display name in Firebase Auth and the Firestore profile."""
    name = display_name.strip()
    if not name:
        return False, "Display name cannot be empty."
    profile = get_user_profile(username)
    firebase_auth.update_user(profile["uid"], display_name=name)
    get_db().collection("users").document(username).update({"display_name": name})
    return True, "Display name updated."


def update_profile(username: str, display_name: str, summary: str) -> tuple[bool, str]:
    """Update the editable public profile fields."""
    name = display_name.strip()
    if not name:
        return False, "Display name cannot be empty."
    profile = get_user_profile(username)
    firebase_auth.update_user(profile["uid"], display_name=name)
    get_db().collection("users").document(username).update({
        "display_name": name,
        "summary": summary.strip(),
    })
    return True, "Profile updated."


def update_password(username: str, current_password: str, new_password: str) -> tuple[bool, str]:
    """Change the Firebase password after verifying the current password."""
    profile = get_user_profile(username)
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    if not _password_token(profile.get("email", ""), current_password):
        return False, "Password verification failed."
    firebase_auth.update_user(profile["uid"], password=new_password)
    return True, "Password changed successfully."


def update_phone(username: str, password: str, phone: str) -> tuple[bool, str]:
    """Save a verified phone number to the user's profile."""
    profile = get_user_profile(username)
    if not phone.strip():
        return False, "Enter a phone number."
    if not _password_token(profile.get("email", ""), password):
        return False, "Password verification failed."
    get_db().collection("users").document(username).update({"phone": phone.strip()})
    return True, "Phone number updated."


def update_email(username: str, password: str, new_email: str) -> tuple[bool, str]:
    """Change email after password verification and send a verification link."""
    import re

    email = new_email.strip().lower()
    profile = get_user_profile(username)
    if _within_profile_cooldown(profile, "email_changed_at"):
        return False, "Email can only be changed once every 24 hours."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Enter a valid email address."
    id_token = _password_token(profile.get("email", ""), password)
    if not id_token:
        return False, "Password verification failed."
    if email == profile.get("email", "").lower():
        return False, "Enter a different email address."
    firebase_auth.update_user(profile["uid"], email=email)
    import requests
    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={_get_web_api_key()}",
        json={"requestType": "VERIFY_EMAIL", "idToken": id_token},
        timeout=10,
    )
    if response.status_code != 200:
        return False, "Email changed, but the verification email could not be sent."
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.collection("email_to_username").document(profile["email"]).delete()
    db.collection("email_to_username").document(email).set({"username": username})
    db.collection("users").document(username).update({"email": email, "email_changed_at": now})
    return True, "Email updated. Check your new inbox for the verification link."


def update_username(username: str, password: str, new_username: str) -> tuple[bool, str, dict | None]:
    """Change username and move the profile's data documents."""
    import re

    new_name = new_username.strip().lower()
    profile = get_user_profile(username)
    if _within_profile_cooldown(profile, "username_changed_at"):
        return False, "Username can only be changed once every 24 hours.", None
    if not re.fullmatch(r"[a-z0-9_.-]{3,30}", new_name):
        return False, "Username must be 3-30 characters using letters, numbers, _, -, or .", None
    if new_name == username:
        return False, "Enter a different username.", None
    if not _password_token(profile.get("email", ""), password):
        return False, "Password verification failed.", None
    db = get_db()
    if db.collection("users").document(new_name).get().exists:
        return False, "Username already taken.", None
    profile["username"] = new_name
    profile["username_changed_at"] = datetime.now(timezone.utc).isoformat()
    old_ref = db.collection("users").document(username)
    new_ref = db.collection("users").document(new_name)
    new_ref.set(profile)
    for doc in old_ref.collection("data").stream():
        new_ref.collection("data").document(doc.id).set(doc.to_dict())
    old_ref.delete()
    db.collection("email_to_username").document(profile["email"]).set({"username": new_name})
    return True, "Username updated.", {
        "username": new_name,
        "display_name": profile.get("display_name", new_name),
        "uid": profile.get("uid", ""),
        "email": profile.get("email", ""),
    }


def save_avatar(username: str, avatar_data: str | None) -> None:
    """Store or remove a small base64 avatar in the profile document."""
    get_db().collection("users").document(username).update({"avatar": avatar_data})


def get_all_users() -> list[str]:
    """Get all registered usernames."""
    db = get_db()
    docs = db.collection("users").stream()
    return [doc.id for doc in docs]


def send_password_reset(email: str) -> tuple[bool, str]:
    """Send a password reset email via Firebase Auth REST API."""
    import requests

    api_key = _get_web_api_key()
    if not api_key:
        return False, "Firebase API key not configured."

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": email,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True, "Password reset email sent! Check your inbox."
        else:
            return False, "Email not found or invalid."
    except Exception as e:
        return False, f"Failed to send reset email: {str(e)}"


# ──────────────────────────────────────────────────────────────────────────────
# Portfolio Data
# ──────────────────────────────────────────────────────────────────────────────

def get_holdings(username: str) -> list:
    """Read holdings from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("holdings").get()
    if doc.exists:
        return doc.to_dict().get("holdings", [])
    return []


def save_holdings_fb(username: str, holdings: list):
    """Save holdings to Firestore."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("holdings").set({
        "holdings": holdings,
    })


def get_transactions_fb(username: str) -> list:
    """Read transactions from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("transactions").get()
    if doc.exists:
        return doc.to_dict().get("transactions", [])
    return []


def save_transactions_fb(username: str, transactions: list):
    """Save transactions to Firestore."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("transactions").set({
        "transactions": transactions,
    })


def get_predictions_fb(username: str) -> list:
    """Read predictions from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("predictions").get()
    if doc.exists:
        return doc.to_dict().get("predictions", [])
    return []


def save_predictions_fb(username: str, predictions: list):
    """Save predictions to Firestore."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("predictions").set({
        "predictions": predictions,
    })


def get_v2_forecasts_fb(username: str) -> list:
    """Read v2 prediction tracker forecasts from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("v2_forecasts").get()
    if doc.exists:
        return doc.to_dict().get("forecasts", [])
    return []


def save_v2_forecasts_fb(username: str, forecasts: list):
    """Save v2 prediction tracker forecasts to Firestore."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("v2_forecasts").set({
        "forecasts": forecasts,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Adaptive Engine (EWMA State)
# ──────────────────────────────────────────────────────────────────────────────

def get_ewma_state(username: str) -> dict:
    """Read EWMA state from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("ewma_state").get()
    if doc.exists:
        return doc.to_dict()
    return {
        "mu_ewma": None,
        "sigma_ewma": None,
        "learning_log": [],
        "days_trained": 0,
    }


def save_ewma_state(username: str, state: dict):
    """Save EWMA state to Firestore."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("ewma_state").set(state)


# ──────────────────────────────────────────────────────────────────────────────
# News Archive
# ──────────────────────────────────────────────────────────────────────────────

def get_news_archive(username: str) -> dict:
    """Read news archive from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("news_archive").get()
    if doc.exists:
        return doc.to_dict()
    return {}


def save_news_archive(username: str, archive: dict):
    """Save news archive to Firestore."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("news_archive").set(archive)


# ──────────────────────────────────────────────────────────────────────────────
# Chat System
# ──────────────────────────────────────────────────────────────────────────────

def get_social(username: str) -> dict:
    """Read social data (friends, requests) from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("social").get()
    if doc.exists:
        return doc.to_dict()
    return {
        "friends": [],
        "requests_sent": [],
        "requests_received": [],
        "chat_ids": [],
    }


def save_social(username: str, social: dict):
    """Save social data to Firestore."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("social").set(social)


def get_chat(chat_id: str) -> dict | None:
    """Read a chat document from Firestore."""
    db = get_db()
    doc = db.collection("chats").document(chat_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def save_chat(chat_id: str, chat: dict):
    """Save a chat document to Firestore."""
    db = get_db()
    db.collection("chats").document(chat_id).set(chat)
    return True


def create_chat(chat_id: str, chat: dict):
    """Create a new chat document in Firestore."""
    db = get_db()
    db.collection("chats").document(chat_id).set(chat)
