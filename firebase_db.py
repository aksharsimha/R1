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
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

# ──────────────────────────────────────────────────────────────────────────────
# Initialization
# ──────────────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_db = None


def init_firebase():
    """Initialize Firebase Admin SDK. Safe to call multiple times."""
    global _db

    if _db is not None:
        return _db

    # Already initialized by another import?
    if firebase_admin._apps:
        _db = firestore.client()
        return _db

    # Try .streamlit/firebase_key.json first (local dev)
    key_path = os.path.join(_HERE, ".streamlit", "firebase_key.json")
    if os.path.exists(key_path):
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        return _db

    # Try Streamlit secrets (cloud deployment)
    try:
        key_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        return _db
    except Exception:
        pass

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
    email_doc = db.collection("email_to_username").document(email).get()
    if not email_doc.exists:
        return False, "Account not found. Please sign up.", None

    username = email_doc.to_dict()["username"]

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


def create_chat(chat_id: str, chat: dict):
    """Create a new chat document in Firestore."""
    db = get_db()
    db.collection("chats").document(chat_id).set(chat)
