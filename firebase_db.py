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
from datetime import datetime, timezone, timedelta
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
    if not username:
        return
    get_db().collection("users").document(username).set({"avatar": avatar_data}, merge=True)


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


# ──────────────────────────────────────────────────────────────────────────────
# Education Progress
# ──────────────────────────────────────────────────────────────────────────────

def get_edu_progress(username: str) -> dict:
    """Read education progress (XP, badges, level) from Firestore."""
    db = get_db()
    doc = db.collection("users").document(username).collection("data").document("edu_progress").get()
    if doc.exists:
        return doc.to_dict()
    return {}


def save_edu_progress(username: str, progress: dict):
    """Save education progress to Firestore and update user profile with XP summary."""
    db = get_db()
    db.collection("users").document(username).collection("data").document("edu_progress").set(progress)
    # Also update the top-level user profile with key metrics for leaderboard queries
    try:
        db.collection("users").document(username).update({
            "total_xp": progress.get("total_xp", 0),
            "edu_level": progress.get("current_level", ""),
            "badges_count": len(progress.get("badges", [])),
            "virtual_balance": progress.get("virtual_balance", 15000.0),
        })
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
# OAuth Connections
# ──────────────────────────────────────────────────────────────────────────────
# Firestore path:  users/{username}/connections/{provider}
#
# Required Firestore security rule (add alongside existing rules):
#
#   match /users/{username}/connections/{provider} {
#     // Any authenticated QUEST user may read connections (public display).
#     allow read: if request.auth != null;
#     // Only the account owner may write or delete their own connections.
#     allow write, delete: if request.auth != null
#                          && request.auth.token.username == username;
#   }
# ──────────────────────────────────────────────────────────────────────────────

def save_oauth_connection(username: str, provider: str, profile_data: dict) -> None:
    """
    Write (or overwrite) an OAuth connection document for a user.

    Firestore path: users/{username}/connections/{provider}

    The document is guaranteed to contain the canonical contract fields:
      provider, provider_user_id, display_name, profile_url, avatar_url,
      verified, connected_at.

    Access tokens are never written — the caller is responsible for ensuring
    none are present in profile_data.

    Args:
        username:     QUEST username (document owner).
        provider:     "discord" | "google" | "linkedin".
        profile_data: Normalised dict produced by oauth_connections._normalise().
    """
    db = get_db()
    try:
        db.collection("users").document(username) \
          .collection("connections").document(provider) \
          .set(profile_data)
    except Exception as exc:
        # Surface the error without crashing — caller may log or display it
        raise RuntimeError(f"Failed to save OAuth connection ({provider}): {exc}") from exc


def get_oauth_connections(username: str) -> dict:
    """
    Return all OAuth connection documents for any QUEST user.

    This is a public read operation intended for profile display — it fetches
    data for *any* username, not just the currently authenticated user.
    Firestore security rules restrict writes to the owner.

    Args:
        username:  Any valid QUEST username.

    Returns:
        Dict[provider_name, connection_dict].
        Empty dict if the user has no connections or on any read error.
    """
    db = get_db()
    try:
        docs = db.collection("users").document(username) \
                 .collection("connections").stream()
        return {doc.id: doc.to_dict() for doc in docs}
    except Exception:
        return {}


def remove_oauth_connection(username: str, provider: str) -> None:
    """
    Delete a single OAuth connection document.

    Firestore path: users/{username}/connections/{provider}

    Args:
        username:  QUEST username (must be the authenticated user; enforced
                   by Firestore security rules at the database level).
        provider:  "discord" | "google" | "linkedin".
    """
    db = get_db()
    try:
        db.collection("users").document(username) \
          .collection("connections").document(provider) \
          .delete()
    except Exception as exc:
        raise RuntimeError(f"Failed to remove OAuth connection ({provider}): {exc}") from exc


# ──────────────────────────────────────────────────────────────────────────────
# Discord-Style Banner & Profile Customization Schema
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_BANNER_CONFIG = {
    "bannerType": "color",          # 'color' | 'image'
    "bannerValue": "#5865F2",       # Discord Blurple default or hex / data URL
    "themeColor": "#5865F2",        # primary / accent hex
    "cardBackground": "#111214",    # Discord dark default
    "isPremium": False,             # Free/Basic vs Pro/Premium tier
    "animationEffect": "none",      # 'none' | 'neon_border' | 'holo_scanline' | 'circuit_surge' | 'rgb_orbit' | 'glitch_aura'
    "animationIntensity": 2,        # 1 (Subtle), 2 (Balanced), 3 (High Voltage)
}



def get_user_quest_coins(username: str) -> int:
    """Get the user's Quest Coins balance from edu_progress or profile."""
    if not username:
        return 0
    try:
        # Check edu_progress in Firestore
        edu_prog = get_edu_progress(username)
        if isinstance(edu_prog, dict) and "quest_coins" in edu_prog:
            return int(edu_prog["quest_coins"])
        # Check user profile in Firestore
        prof = get_user_profile(username)
        if isinstance(prof, dict) and "quest_coins" in prof:
            return int(prof["quest_coins"])
        # Check local edu_db
        try:
            import edu_db
            local_prog = edu_db.load_progress()
            if isinstance(local_prog, dict) and "quest_coins" in local_prog:
                return int(local_prog["quest_coins"])
        except Exception:
            pass
        return 0
    except Exception:
        return 0


def deduct_user_quest_coins(username: str, amount: int) -> tuple[bool, int, str]:
    """Deduct Quest Coins from user account. Returns (success, new_balance, message)."""
    if not username or amount <= 0:
        return False, 0, "Invalid parameters."
    try:
        current_coins = get_user_quest_coins(username)
        if current_coins < amount:
            return False, current_coins, f"Insufficient Quest Coins. Top up your wallet to continue"
        new_balance = current_coins - amount

        db = get_db()
        # 1. Update Firestore edu_progress
        edu_prog = get_edu_progress(username) or {}
        edu_prog["quest_coins"] = new_balance
        save_edu_progress(username, edu_prog)

        # 2. Update Firestore user profile
        db.collection("users").document(username).set({
            "quest_coins": new_balance
        }, merge=True)

        # 3. Update local edu_db if available
        try:
            import edu_db
            local_prog = edu_db.load_progress()
            local_prog["quest_coins"] = new_balance
            edu_db.save_progress(local_prog)
        except Exception:
            pass

        return True, new_balance, f"Successfully deducted {amount:,} Quest Coins. New balance: {new_balance:,} coins."
    except Exception as e:
        return False, 0, f"Failed to deduct coins: {e}"


def get_premium_status(username: str) -> dict:
    """
    Check if user's Premium subscription is active, calculate remaining days,
    and automatically handle expiration.
    """
    if not username:
        return {"is_active": False, "expires_at": None, "remaining_days": 0, "is_expired": False, "formatted_expiry": ""}
    try:
        profile = get_user_profile(username)
        stored_custom = profile.get("banner_customization", {})
        if not isinstance(stored_custom, dict):
            stored_custom = {}

        exp_raw = (
            profile.get("premium_expires_at")
            or profile.get("premiumExpiresAt")
            or stored_custom.get("premiumExpiresAt")
            or stored_custom.get("premium_expires_at")
        )

        exp_dt = None
        if exp_raw:
            if hasattr(exp_raw, "date"):
                exp_dt = exp_raw
            elif isinstance(exp_raw, (int, float)):
                ts = exp_raw / 1000.0 if exp_raw > 1e11 else exp_raw
                exp_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(exp_raw, str):
                exp_dt = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))

        now = datetime.now(timezone.utc)
        if exp_dt:
            if getattr(exp_dt, "tzinfo", None) is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)

            if now > exp_dt:
                # Expired! Automatically downgrade user in Firestore
                set_pro_status(username, False)
                db = get_db()
                db.collection("users").document(username).set({
                    "is_premium": False,
                    "is_pro": False,
                    "banner_customization": {"isPremium": False},
                }, merge=True)
                return {
                    "is_active": False,
                    "expires_at": exp_dt,
                    "remaining_days": 0,
                    "is_expired": True,
                    "formatted_expiry": exp_dt.strftime("%b %d, %Y"),
                }
            else:
                # Active!
                remaining_days = max(1, (exp_dt.date() - now.date()).days)
                return {
                    "is_active": True,
                    "expires_at": exp_dt,
                    "remaining_days": remaining_days,
                    "is_expired": False,
                    "formatted_expiry": exp_dt.strftime("%b %d, %Y"),
                }
        else:
            is_p = bool(
                profile.get("is_pro")
                or profile.get("is_premium")
                or stored_custom.get("isPremium")
            )
            return {
                "is_active": is_p,
                "expires_at": None,
                "remaining_days": 999 if is_p else 0,
                "is_expired": False,
                "formatted_expiry": "Active" if is_p else "",
            }
    except Exception as e:
        print(f"[firebase_db] Error checking premium status: {e}")
        return {"is_active": False, "expires_at": None, "remaining_days": 0, "is_expired": False, "formatted_expiry": ""}


def get_premium_trial_status(username: str, trial_seconds: int = 300) -> dict:
    """
    Check if the user has started a 5-minute (300-second) one-time free Premium preview trial,
    and return whether it is currently active, expired, or unused.
    """
    if not username:
        return {"started": False, "is_active": False, "is_expired": False, "seconds_remaining": 0, "started_at": None}
    try:
        profile = get_user_profile(username)
        trial_raw = profile.get("premium_trial_started_at") or profile.get("preview_trial_started_at")
        if not trial_raw:
            return {"started": False, "is_active": False, "is_expired": False, "seconds_remaining": trial_seconds, "started_at": None}

        trial_dt = None
        if hasattr(trial_raw, "date"):
            trial_dt = trial_raw
        elif isinstance(trial_raw, (int, float)):
            ts = trial_raw / 1000.0 if trial_raw > 1e11 else trial_raw
            trial_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(trial_raw, str):
            trial_dt = datetime.fromisoformat(trial_raw.replace("Z", "+00:00"))

        if trial_dt:
            if getattr(trial_dt, "tzinfo", None) is None:
                trial_dt = trial_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            elapsed = (now - trial_dt).total_seconds()
            if elapsed < trial_seconds:
                remaining = int(trial_seconds - elapsed)
                return {
                    "started": True,
                    "is_active": True,
                    "is_expired": False,
                    "seconds_remaining": remaining,
                    "started_at": trial_dt,
                }
            else:
                return {
                    "started": True,
                    "is_active": False,
                    "is_expired": True,
                    "seconds_remaining": 0,
                    "started_at": trial_dt,
                }
        return {"started": False, "is_active": False, "is_expired": False, "seconds_remaining": trial_seconds, "started_at": None}
    except Exception as e:
        print(f"[firebase_db] Error checking trial status: {e}")
        return {"started": False, "is_active": False, "is_expired": False, "seconds_remaining": 0, "started_at": None}


def start_premium_trial(username: str) -> tuple[bool, str, dict]:
    """
    Start the 5-minute one-time free Premium preview trial for a user.
    If already used or started, it cannot be restarted.
    """
    if not username:
        return False, "Invalid username.", {}
    status = get_premium_trial_status(username)
    if status["started"]:
        if status["is_active"]:
            return True, f"Trial already active ({status['seconds_remaining']}s remaining).", status
        else:
            return False, "5-Minute Free Trial has already been used and is locked.", status

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    try:
        db = get_db()
        db.collection("users").document(username).set({
            "premium_trial_started_at": now_iso,
        }, merge=True)
        new_status = {
            "started": True,
            "is_active": True,
            "is_expired": False,
            "seconds_remaining": 300,
            "started_at": now,
        }
        return True, "5-Minute Free Premium Trial started!", new_status
    except Exception as e:
        return False, f"Failed to start trial: {e}", {}


def upgrade_user_to_premium(username: str, duration_days: int = 30, cost_coins: int = 1000) -> tuple[bool, str, dict]:
    """
    Upgrade or extend user to Premium for duration_days by deducting cost_coins.
    Returns (success, message, result_dict).
    """
    if not username:
        return False, "Invalid username.", {}

    # 1. Check & Deduct Coins
    ok, new_bal, msg = deduct_user_quest_coins(username, cost_coins)
    if not ok:
        return False, "Insufficient Quest Coins. Top up your wallet to continue", {}

    try:
        now = datetime.now(timezone.utc)
        status = get_premium_status(username)
        if status["is_active"] and status["expires_at"]:
            new_expiry = status["expires_at"] + timedelta(days=duration_days)
        else:
            new_expiry = now + timedelta(days=duration_days)

        expiry_iso = new_expiry.isoformat()

        # 2. Persist to Firestore
        db = get_db()
        db.collection("users").document(username).set({
            "is_premium": True,
            "is_pro": True,
            "premium_expires_at": expiry_iso,
            "banner_customization": {
                "isPremium": True,
                "premiumExpiresAt": expiry_iso,
            },
            "profile_customization": {
                "is_pro": True,
                "show_pro_badge": True,
            }
        }, merge=True)

        remaining_days = max(1, (new_expiry.date() - now.date()).days)
        res = {
            "is_active": True,
            "expires_at": new_expiry,
            "remaining_days": remaining_days,
            "formatted_expiry": new_expiry.strftime("%b %d, %Y"),
            "new_coins_balance": new_bal,
        }
        return True, f"🎉 Successfully upgraded to Premium for {duration_days} days! (Expires {new_expiry.strftime('%b %d, %Y')})", res
    except Exception as e:
        return False, f"Upgrade failed: {e}", {}


def is_user_pro(username: str) -> bool:
    """Check if a user has an active Pro subscription with auto-expiration check."""
    if not username:
        return False
    try:
        status = get_premium_status(username)
        return bool(status.get("is_active", False))
    except Exception:
        return False


def set_pro_status(username: str, is_pro: bool = True) -> bool:
    """Set Pro subscription status in Firestore."""
    if not username:
        return False
    try:
        db = get_db()
        db.collection("users").document(username).set({
            "is_pro": is_pro,
            "is_premium": is_pro,
            "profile_customization": {"is_pro": is_pro}
        }, merge=True)
        return True
    except Exception as e:
        print(f"[firebase_db] Failed to set pro status: {e}")
        return False


def get_banner_customization(username: str) -> dict:
    """Read Discord-style banner & profile customization from Firestore with legacy fallback."""
    if not username or not username.strip():
        return dict(_DEFAULT_BANNER_CONFIG)
    try:
        profile = get_user_profile(username)
        stored = profile.get("banner_customization", {})
        if not isinstance(stored, dict):
            stored = {}
        legacy = profile.get("profile_customization", {})
        if not isinstance(legacy, dict):
            legacy = {}

        res = dict(_DEFAULT_BANNER_CONFIG)

        # Legacy profile_customization hydration
        if legacy.get("accent_color"):
            res["themeColor"] = legacy["accent_color"]
            res["cardBackground"] = legacy.get("card_bg") or legacy["accent_color"]
            res["bannerValue"] = legacy["accent_color"]
        if legacy.get("banner_url"):
            b_url = str(legacy["banner_url"])
            if b_url.startswith("http") or b_url.startswith("data:"):
                res["bannerType"] = "image"
                res["bannerValue"] = b_url
        if legacy.get("profile_effect"):
            eff = legacy["profile_effect"]
            if eff in ["subtle_glow", "neon_border"]:
                res["animationEffect"] = "neon_border"
            elif eff in ["scanline", "holo_scanline"]:
                res["animationEffect"] = "holo_scanline"
            elif eff in ["matrix", "circuit_surge"]:
                res["animationEffect"] = "circuit_surge"
            elif eff in ["chroma", "rgb_orbit"]:
                res["animationEffect"] = "rgb_orbit"
            elif eff in ["glitch", "glitch_aura"]:
                res["animationEffect"] = "glitch_aura"

        # Stored banner_customization takes precedence
        res.update(stored)

        if profile.get("profile_customization", {}).get("is_pro") or profile.get("is_pro") or profile.get("is_premium") or stored.get("isPremium") or legacy.get("is_pro"):
            res["isPremium"] = True
        return res
    except Exception:
        return dict(_DEFAULT_BANNER_CONFIG)


def save_banner_customization(username: str, data: dict) -> bool:
    """Save banner customization dict to Firestore user document and sync across schemas."""
    if not username or not username.strip():
        return False
    try:
        db = get_db()
        clean = {}
        for k in _DEFAULT_BANNER_CONFIG:
            if k in data:
                clean[k] = data[k]

        theme_c = clean.get("themeColor") or clean.get("cardBackground") or "#5865F2"
        is_p = bool(clean.get("isPremium", False))

        db.collection("users").document(username).set({
            "banner_customization": clean,
            "profile_customization": {
                "accent_color": theme_c,
                "is_pro": is_p,
                "banner_url": clean.get("bannerValue") if clean.get("bannerType") == "image" else theme_c,
                "profile_theme": "custom",
                "profile_effect": clean.get("animationEffect", "none"),
                "show_pro_badge": is_p,
            },
            "is_pro": is_p,
            "is_premium": is_p,
        }, merge=True)
        return True
    except Exception as e:
        print(f"[firebase_db] Failed to save banner customization: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Entitlements Management
# ──────────────────────────────────────────────────────────────────────────────

STANDARD_ENTITLEMENT_KEYS = ["premium", "ad_free", "news_access", "intl_stocks"]


def get_user_entitlements(username: str) -> dict:
    """
    Get user's entitlements mapping {key: expiry_iso or None}.
    Keys: 'premium', 'ad_free', 'news_access', 'intl_stocks'.
    Checks Firestore and mirrors/falls back to local edu_db.
    """
    res = {k: None for k in STANDARD_ENTITLEMENT_KEYS}
    if not username:
        return res

    # 1. Local edu_db baseline / offline check
    try:
        import edu_db
        local_prog = edu_db.load_progress()
        if isinstance(local_prog, dict):
            local_ent = local_prog.get("entitlements", {})
            if isinstance(local_ent, dict):
                for k, v in local_ent.items():
                    res[k] = v
    except Exception:
        pass

    # 2. Firestore profile check
    try:
        profile = get_user_profile(username)
        if isinstance(profile, dict):
            stored_ent = profile.get("entitlements", {})
            if isinstance(stored_ent, dict):
                for k, v in stored_ent.items():
                    res[k] = v
            # If premium is stored directly in profile or banner_customization
            if not res.get("premium"):
                prem_status = get_premium_status(username)
                if prem_status.get("is_active"):
                    exp = prem_status.get("expires_at")
                    res["premium"] = exp.isoformat() if hasattr(exp, "isoformat") else "active"
    except Exception as e:
        print(f"[firebase_db] Error reading entitlements for {username}: {e}")

    return res


def has_entitlement(username: str, key: str) -> bool:
    """Check if a user has an active entitlement for the given key, verifying expiration."""
    if not username or not key:
        return False
    try:
        if key == "premium":
            prem = get_premium_status(username)
            if prem.get("is_active"):
                return True

        entitlements = get_user_entitlements(username)
        exp_raw = entitlements.get(key)
        if not exp_raw:
            return False

        if isinstance(exp_raw, bool):
            return exp_raw
        if str(exp_raw).lower() in ["true", "active", "lifetime", "permanent"]:
            return True

        exp_dt = None
        if hasattr(exp_raw, "date"):
            exp_dt = exp_raw
        elif isinstance(exp_raw, (int, float)):
            ts = exp_raw / 1000.0 if exp_raw > 1e11 else exp_raw
            exp_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(exp_raw, str):
            exp_dt = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))

        if exp_dt:
            if getattr(exp_dt, "tzinfo", None) is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return now <= exp_dt

        return False
    except Exception as e:
        print(f"[firebase_db] Error checking entitlement {key} for {username}: {e}")
        return False


def grant_entitlement(username: str, key: str, duration_days: int = 30, cost_coins: int = 0) -> tuple[bool, str, dict]:
    """
    Grant or extend an entitlement for duration_days by deducting cost_coins via deduct_user_quest_coins().
    Atomically writes to Firestore and mirrors to local edu_db.
    Returns (ok, msg, data).
    """
    if not username or not key:
        return False, "Invalid username or entitlement key.", {}

    # 1. Deduct coins if cost_coins > 0
    if cost_coins > 0:
        ok, new_bal, msg = deduct_user_quest_coins(username, cost_coins)
        if not ok:
            return False, msg, {}
    else:
        new_bal = get_user_quest_coins(username)

    try:
        now = datetime.now(timezone.utc)
        
        # Check current expiry to extend if active
        entitlements = get_user_entitlements(username)
        cur_exp_raw = entitlements.get(key)
        exp_dt = None
        if cur_exp_raw:
            try:
                if hasattr(cur_exp_raw, "date"):
                    exp_dt = cur_exp_raw
                elif isinstance(cur_exp_raw, (int, float)):
                    ts = cur_exp_raw / 1000.0 if cur_exp_raw > 1e11 else cur_exp_raw
                    exp_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                elif isinstance(cur_exp_raw, str) and cur_exp_raw not in ["active", "lifetime"]:
                    exp_dt = datetime.fromisoformat(cur_exp_raw.replace("Z", "+00:00"))
            except Exception:
                exp_dt = None

        if exp_dt:
            if getattr(exp_dt, "tzinfo", None) is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt > now:
                new_expiry = exp_dt + timedelta(days=duration_days)
            else:
                new_expiry = now + timedelta(days=duration_days)
        else:
            new_expiry = now + timedelta(days=duration_days)

        expiry_iso = new_expiry.isoformat()
        entitlements[key] = expiry_iso

        # 2. Persist to Firestore user document
        try:
            db = get_db()
            if db:
                user_doc_update = {
                    "entitlements": entitlements,
                }
                if key == "premium":
                    user_doc_update.update({
                        "is_premium": True,
                        "is_pro": True,
                        "premium_expires_at": expiry_iso,
                        "banner_customization": {
                            "isPremium": True,
                            "premiumExpiresAt": expiry_iso,
                        },
                        "profile_customization": {
                            "is_pro": True,
                            "show_pro_badge": True,
                        }
                    })
                db.collection("users").document(username).set(user_doc_update, merge=True)
        except Exception as e:
            print(f"[firebase_db] Warning: Could not update Firestore user doc: {e}")

        # 3. Update Firestore edu_progress
        try:
            edu_prog = get_edu_progress(username) or {}
            edu_prog_ent = edu_prog.get("entitlements", {})
            if not isinstance(edu_prog_ent, dict):
                edu_prog_ent = {}
            edu_prog_ent[key] = expiry_iso
            edu_prog["entitlements"] = edu_prog_ent
            save_edu_progress(username, edu_prog)
        except Exception:
            pass

        # 4. Mirror to local edu_db progress
        try:
            import edu_db
            local_prog = edu_db.load_progress()
            if isinstance(local_prog, dict):
                local_ent = local_prog.get("entitlements", {})
                if not isinstance(local_ent, dict):
                    local_ent = {}
                local_ent[key] = expiry_iso
                local_prog["entitlements"] = local_ent
                edu_db.save_progress(local_prog)
        except Exception:
            pass

        res_data = {
            "key": key,
            "is_active": True,
            "expires_at": expiry_iso,
            "duration_days": duration_days,
            "new_coins_balance": new_bal,
        }
        return True, f"Successfully granted '{key}' for {duration_days} days.", res_data

    except Exception as e:
        return False, f"Failed to grant entitlement: {e}", {}

