"""
QUEST — OAuth Account Connections
===================================
STABLE PUBLIC API (for external consumers, e.g. User Profile Popup):
  - get_public_connections(username: str) -> list[dict]
      Returns a list of public connection dicts sorted by connected_at ascending.
      Cached in session_state with a 60-second TTL. Never raises.
  - PROVIDER_META: dict[str, dict]
      Provider display metadata: label, icon_svg (inline SVG), and brand_color.
  - render_connection_badges(username: str, compact: bool = False) -> str
      Returns ready-to-render HTML badge string styled with var(--q-*) tokens.

All other functions, constants, and helpers in this module are internal
implementation details and subject to change without notice.

Overview:
  Links external provider accounts (Discord, Google, LinkedIn) to an existing
  QUEST profile for public display. This is NOT a login flow — users must
  already be authenticated into QUEST before initiating a link.

Flow:
  1. UI calls build_auth_url(provider, username) -> redirects user to provider.
  2. Provider redirects back with ?code=...&state=... query params.
  3. UI calls handle_callback(username) -> validates CSRF nonce, exchanges
     code for token (in-memory only), fetches public profile, saves sanitised
     fields to Firestore, clears query params, returns the saved dict.

Firestore path: users/{username}/connections/{provider}

Firestore security rules required (add to your rules file):
  match /users/{username}/connections/{provider} {
    // Any authenticated QUEST user may read connections (public display).
    allow read: if request.auth != null;
    // Only the account owner may write or delete their own connections.
    allow write, delete: if request.auth != null
                         && request.auth.token.username == username;
  }

Secrets required in .streamlit/secrets.toml:
  [oauth]
  discord_client_id      = "..."
  discord_client_secret  = "..."
  google_client_id       = "..."
  google_client_secret   = "..."
  linkedin_client_id     = "..."
  linkedin_client_secret = "..."
  redirect_uri           = "https://your-app.streamlit.app/"  # one URI for all
"""

from __future__ import annotations

import html
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
import streamlit as st

import firebase_db

# ------------------------------------------------------------------------------
# Stable Public Metadata
# ------------------------------------------------------------------------------

PROVIDER_META: dict[str, dict[str, str]] = {
    "discord": {
        "label": "Discord",
        "brand_color": "#5865F2",
        "icon_svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">'
            '<path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.894a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>'
            '</svg>'
        ),
    },
    "google": {
        "label": "Google",
        "brand_color": "#4285F4",
        "icon_svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">'
            '<path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"/>'
            '</svg>'
        ),
    },
    "linkedin": {
        "label": "LinkedIn",
        "brand_color": "#0A66C2",
        "icon_svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">'
            '<path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 10.9v8.37H9.2V10.9H6.46M7.83 6.45c-.94 0-1.7.76-1.7 1.7 0 .94.76 1.7 1.7 1.7.94 0 1.7-.76 1.7-1.7 0-.94-.76-1.7-1.7-1.7z"/>'
            '</svg>'
        ),
    },
}

# ------------------------------------------------------------------------------
# Provider configuration
# ------------------------------------------------------------------------------

_PROVIDERS: dict[str, dict] = {
    "discord": {
        "authorize_url": "https://discord.com/oauth2/authorize",
        "token_url":     "https://discord.com/api/oauth2/token",
        "userinfo_url":  "https://discord.com/api/users/@me",
        "scope":         "identify",
    },
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":     "https://oauth2.googleapis.com/token",
        "userinfo_url":  "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope":         "openid email profile",
    },
    "linkedin": {
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url":     "https://www.linkedin.com/oauth/v2/accessToken",
        "userinfo_url":  "https://api.linkedin.com/v2/userinfo",
        "scope":         "openid profile email",
    },
}

_VALID_PROVIDERS = frozenset(_PROVIDERS)

# Session-state key for CSRF nonce storage
_STATE_KEY = "_oauth_state"


# ------------------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------------------

def _secrets() -> dict:
    """Return the [oauth] secrets table, raising a clear error if absent."""
    try:
        return dict(st.secrets["oauth"])
    except (KeyError, Exception) as exc:
        raise RuntimeError(
            "OAuth secrets missing. Add an [oauth] section to .streamlit/secrets.toml."
        ) from exc


def _client_id(provider: str) -> str:
    return _secrets()[f"{provider}_client_id"]


def _client_secret(provider: str) -> str:
    return _secrets()[f"{provider}_client_secret"]


def _redirect_uri() -> str:
    return _secrets()["redirect_uri"]


def _exchange_code(provider: str, code: str) -> str | None:
    """
    Exchange an authorization code for an access token.
    Returns the access_token string, or None on failure.
    Tokens are NEVER stored — used only within the lifetime of this call.
    """
    cfg = _PROVIDERS[provider]
    try:
        resp = requests.post(
            cfg["token_url"],
            data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  _redirect_uri(),
                "client_id":     _client_id(provider),
                "client_secret": _client_secret(provider),
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        st.error(f"OAuth token exchange failed for {provider}: {exc}")
        return None


def _fetch_userinfo(provider: str, access_token: str) -> dict | None:
    """
    Fetch the provider's userinfo endpoint.
    Returns the raw JSON dict, or None on failure.
    """
    cfg = _PROVIDERS[provider]
    try:
        resp = requests.get(
            cfg["userinfo_url"],
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"OAuth userinfo fetch failed for {provider}: {exc}")
        return None


def _normalise(provider: str, raw: dict) -> dict:
    """
    Convert raw provider userinfo into the canonical Firestore document shape.
    Tokens are never included.  Timestamp is set here, not by the provider.
    """
    now = datetime.now(timezone.utc)

    if provider == "discord":
        uid      = str(raw.get("id", ""))
        name     = raw.get("global_name") or raw.get("username", "")
        handle   = raw.get("username", "")
        avatar_h = raw.get("avatar", "")
        avatar   = (
            f"https://cdn.discordapp.com/avatars/{uid}/{avatar_h}.png"
            if uid and avatar_h else ""
        )
        return {
            "provider":          "discord",
            "provider_user_id":  uid,
            "display_name":      name or handle,
            "profile_url":       "",          # Discord has no public profile URL
            "avatar_url":        avatar,
            "verified":          True,
            "connected_at":      now,
            # Extra field for display richness (not part of the contract minimum)
            "_discord_username": handle,
        }

    if provider == "google":
        return {
            "provider":         "google",
            "provider_user_id": str(raw.get("sub", "")),
            "display_name":     raw.get("name", ""),
            "profile_url":      "",           # Requires additional scopes not requested
            "avatar_url":       raw.get("picture", ""),
            "verified":         True,
            "connected_at":     now,
            "_google_email":    raw.get("email", ""),
        }

    if provider == "linkedin":
        return {
            "provider":          "linkedin",
            "provider_user_id":  str(raw.get("sub", "")),
            "display_name":      raw.get("name", ""),
            "profile_url":       "",          # Requires r_liteprofile; not in openid scope
            "avatar_url":        raw.get("picture", ""),
            "verified":          True,
            "connected_at":      now,
            "_linkedin_email":   raw.get("email", ""),
        }

    raise ValueError(f"Unknown provider: {provider!r}")


def _clear_callback_params() -> None:
    """Remove OAuth query params from the URL."""
    for key in ("code", "state", "error", "error_description"):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass


# ------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------

def build_auth_url(provider: str, username: str) -> str:
    """
    Generate and return the provider's OAuth authorization URL.

    A cryptographically random CSRF nonce is generated and stored in
    st.session_state[_STATE_KEY].  The state param sent to the provider is
    "<provider>:<nonce>" so the callback can identify the provider without a
    separate server-side lookup.

    Args:
        provider:  One of "discord", "google", "linkedin".
        username:  The current QUEST username (recorded for post-callback use).

    Returns:
        Full authorization URL string to redirect the user to.

    Raises:
        ValueError:   For unknown providers.
        RuntimeError: If OAuth secrets are not configured.
    """
    if provider not in _VALID_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider!r}")

    nonce = secrets.token_urlsafe(32)
    state_store = st.session_state.get(_STATE_KEY)
    if isinstance(state_store, dict):
        state_store[provider] = nonce
    elif isinstance(state_store, str):
        st.session_state[_STATE_KEY] = {"_legacy": state_store, provider: nonce}
    else:
        st.session_state[_STATE_KEY] = {provider: nonce}
    st.session_state["_oauth_username"] = username  # remember who initiated

    cfg = _PROVIDERS[provider]
    params = {
        "client_id":     _client_id(provider),
        "redirect_uri":  _redirect_uri(),
        "response_type": "code",
        "scope":         cfg["scope"],
        "state":         f"{provider}:{nonce}",
    }
    # Google: prompt=consent ensures we always get a fresh grant confirmation.
    if provider == "google":
        params["access_type"] = "online"
        params["prompt"] = "consent"

    return f"{cfg['authorize_url']}?{urlencode(params)}"


def handle_callback(username: str) -> dict | None:
    """
    Process the OAuth callback that the provider sends back to the redirect URI.

    Reads st.query_params for "code" and "state":
    - Validates "state" against the stored CSRF nonce (rejects on mismatch).
    - Exchanges "code" for an access token (token is NEVER stored).
    - Fetches the provider's userinfo endpoint.
    - Normalises and persists the public profile fields to Firestore.
    - Clears OAuth-related query params from the URL.

    Args:
        username:  The current QUEST username to attach the connection to.

    Returns:
        The saved connection dict on success.
        None if no "code" param is present (i.e. not a callback page load).
        Shows st.error and returns None on validation or network failures.
    """
    params = st.query_params
    code  = params.get("code")
    state = params.get("state", "")

    if not code:
        return None  # Not a callback — ordinary page load

    # ── CSRF validation ────────────────────────────────────────────────────
    stored_state = st.session_state.get(_STATE_KEY)
    if not stored_state:
        st.error("OAuth error: no CSRF nonce in session. The link may have expired — please try again.")
        _clear_callback_params()
        return None

    if ":" not in state:
        st.error("OAuth error: malformed state parameter received. Possible CSRF attempt — request rejected.")
        _clear_callback_params()
        return None

    provider, received_nonce = state.split(":", 1)

    if provider not in _VALID_PROVIDERS:
        st.error(f"OAuth error: unknown provider '{provider}' in state.")
        _clear_callback_params()
        return None

    if isinstance(stored_state, dict):
        stored_nonce = stored_state.get(provider)
    else:
        stored_nonce = stored_state

    if not stored_nonce or not secrets.compare_digest(received_nonce, stored_nonce):
        st.error("OAuth error: state mismatch — request rejected (possible CSRF).")
        _clear_callback_params()
        return None

    # Nonce consumed — discard immediately so it cannot be replayed
    if isinstance(st.session_state.get(_STATE_KEY), dict):
        st.session_state[_STATE_KEY].pop(provider, None)
    else:
        st.session_state.pop(_STATE_KEY, None)

    # ── Token exchange (token lives only in this local scope) ──────────────
    access_token = _exchange_code(provider, code)
    if not access_token:
        _clear_callback_params()
        return None  # st.error already shown by _exchange_code

    # ── Fetch public profile (token referenced and discarded here) ─────────
    raw = _fetch_userinfo(provider, access_token)
    # access_token is not referenced again after this line
    del access_token
    if not raw:
        _clear_callback_params()
        return None  # st.error already shown by _fetch_userinfo

    # ── Persist sanitised fields; no token fields reach Firestore ──────────
    normalised = _normalise(provider, raw)
    save_connection(username, provider, normalised)

    _clear_callback_params()
    return normalised


def save_connection(username: str, provider: str, profile_data: dict) -> None:
    """
    Write a connection document to users/{username}/connections/{provider}.

    The document must match the canonical field contract:
      provider, provider_user_id, display_name, profile_url, avatar_url,
      verified, connected_at.

    Additional "_*" fields may be present for display richness.
    """
    firebase_db.save_oauth_connection(username, provider, profile_data)
    _invalidate_cache(username)


def get_connections(username: str) -> dict:
    """
    Return all OAuth connections for *any* QUEST user (public read).

    This is intended for public display — e.g. showing linked badges on
    another user's profile page.  No auth check is performed here; Firestore
    security rules enforce read access at the database level.

    Args:
        username:  Any valid QUEST username.

    Returns:
        Dict[provider_name, connection_dict].  Empty dict if none exist or
        on Firestore error.
    """
    return firebase_db.get_oauth_connections(username)


def remove_connection(username: str, provider: str) -> None:
    """
    Delete a provider connection for the given user.

    The caller is responsible for ensuring username matches the currently
    authenticated QUEST user.  Firestore security rules enforce ownership
    at the database level.

    Args:
        username:  QUEST username (must be the currently authenticated user).
        provider:  One of "discord", "google", "linkedin".
    """
    firebase_db.remove_oauth_connection(username, provider)
    _invalidate_cache(username)


# ------------------------------------------------------------------------------
# Stable Public Interface for UI Components (Profile Popup, Badges, etc.)
# ------------------------------------------------------------------------------

_PUBLIC_CONN_TTL = 60.0  # seconds


def _invalidate_cache(username: str) -> None:
    """Remove a user's cached connections from session_state."""
    try:
        cache = st.session_state.get("_public_conn_cache")
        if isinstance(cache, dict):
            cache.pop(username.strip().lower(), None)
    except Exception:
        pass


def _store_cache(username: str, data: list[dict], ts: float) -> None:
    """Store fetched connections in session_state with timestamp."""
    try:
        if "_public_conn_cache" not in st.session_state or not isinstance(st.session_state["_public_conn_cache"], dict):
            st.session_state["_public_conn_cache"] = {}
        st.session_state["_public_conn_cache"][username] = (data, ts)
    except Exception:
        pass


def get_public_connections(username: str) -> list[dict]:
    """
    Return a list of public connection records for a user, sorted by
    connected_at ascending.

    Cached in st.session_state with a 60-second TTL to avoid hitting Firestore
    on every popup render.

    Each item in the returned list contains exactly:
      {
        "provider": str,
        "display_name": str,
        "profile_url": str,
        "avatar_url": str,
        "verified": bool,
      }

    Returns [] on any error or if the user has none. Never raises.
    """
    if not username or not isinstance(username, str):
        return []

    clean_user = username.strip().lower()
    now_ts = time.time()

    # 1. Check in-memory session cache
    try:
        cache = st.session_state.get("_public_conn_cache")
        if isinstance(cache, dict) and clean_user in cache:
            cached_data, cached_ts = cache[clean_user]
            if (now_ts - cached_ts) < _PUBLIC_CONN_TTL:
                return [dict(item) for item in cached_data]
    except Exception:
        pass

    # 2. Fetch from Firestore
    try:
        raw_conns = get_connections(clean_user)
        if not raw_conns or not isinstance(raw_conns, dict):
            _store_cache(clean_user, [], now_ts)
            return []

        def _sort_key(item: dict) -> float:
            cat = item.get("connected_at")
            if hasattr(cat, "timestamp"):
                return float(cat.timestamp())
            if isinstance(cat, datetime):
                return float(cat.timestamp())
            if isinstance(cat, (int, float)):
                return float(cat)
            if isinstance(cat, str):
                try:
                    return float(datetime.fromisoformat(cat.replace("Z", "+00:00")).timestamp())
                except Exception:
                    return 0.0
            return 0.0

        sorted_raw = sorted(raw_conns.values(), key=_sort_key)

        result: list[dict] = [
            {
                "provider": str(c.get("provider", "")),
                "display_name": str(c.get("display_name", "")),
                "profile_url": str(c.get("profile_url", "")),
                "avatar_url": str(c.get("avatar_url", "")),
                "verified": bool(c.get("verified", True)),
            }
            for c in sorted_raw
            if isinstance(c, dict) and c.get("provider")
        ]

        _store_cache(clean_user, result, now_ts)
        return [dict(item) for item in result]
    except Exception:
        return []


def render_connection_badges(username: str, compact: bool = False) -> str:
    """
    Return an HTML string containing the rendered badge row for a user.

    Does NOT call st.markdown itself, allowing the caller to control placement.
    compact=True: renders icons only.
    compact=False: renders icon plus display_name.
    Each badge links to profile_url when present.
    Styled with var(--q-*) tokens; brand_color is used only for icon fill.

    Returns "" if the user has no connections. Never raises.
    """
    try:
        conns = get_public_connections(username)
        if not conns:
            return ""

        badges: list[str] = []
        for c in conns:
            provider = c.get("provider", "")
            meta = PROVIDER_META.get(provider, {})
            label = meta.get("label", provider.title())
            icon_svg = meta.get("icon_svg", "")
            brand_color = meta.get("brand_color", "currentColor")
            disp_name = c.get("display_name") or label
            profile_url = c.get("profile_url", "").strip()

            esc_label = html.escape(label)
            esc_disp = html.escape(disp_name)
            title_attr = f' title="{esc_label}: {esc_disp}"'

            icon_span = f'<span style="display:inline-flex;align-items:center;color:{brand_color};line-height:1;">{icon_svg}</span>'

            if compact:
                inner = icon_span
                pad = "4px 6px"
                radius = "6px"
            else:
                inner = (
                    f'{icon_span}'
                    f'<span style="font-size:0.75rem;font-weight:500;color:var(--q-text);">{esc_disp}</span>'
                )
                if c.get("verified"):
                    inner += '<span style="color:var(--q-accent);font-size:0.7rem;line-height:1;" title="Verified">✓</span>'
                pad = "3px 8px"
                radius = "999px"

            base_style = (
                f"display:inline-flex;align-items:center;gap:5px;padding:{pad};"
                f"background:var(--q-surface-2);border:1px solid var(--q-border);"
                f"border-radius:{radius};box-sizing:border-box;vertical-align:middle;"
            )

            if profile_url:
                esc_url = html.escape(profile_url)
                badge_html = (
                    f'<a href="{esc_url}" target="_blank" rel="noopener noreferrer"'
                    f' style="{base_style}text-decoration:none;cursor:pointer;"{title_attr}>'
                    f'{inner}</a>'
                )
            else:
                badge_html = f'<span style="{base_style}"{title_attr}>{inner}</span>'

            badges.append(badge_html)

        return (
            '<div class="q-connection-badges" style="display:inline-flex;align-items:center;'
            'gap:6px;flex-wrap:wrap;">' + "".join(badges) + "</div>"
        )
    except Exception:
        return ""

