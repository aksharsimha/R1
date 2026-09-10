import base64

import streamlit as st

import firebase_db
import oauth_connections
import ui_theme


_SECTIONS = ["Profile", "Connections", "Theme"]


@st.dialog("Log Out", dismissible=False)
def _signout_dialog() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stDialog"] button[aria-label="Close"],
        [data-testid="stModal"] button[aria-label="Close"],
        button[aria-label="Close"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.write("Are you sure you want to log out?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_signout_dialog = False
            st.rerun()
    with c2:
        if st.button("Log Out", type="primary", use_container_width=True):
            # We purposely do NOT call remove_remembered_account here.
            # This allows the account to stay in the multi-account cookie (so it appears in the Switcher).
            _preserve_keys = {"auth_cookie_override", "cookie_controller"}
            for key in list(st.session_state.keys()):
                if key not in _preserve_keys:
                    del st.session_state[key]
            st.query_params["page"] = "Overview"
            st.query_params.pop("return_to", None)
            st.session_state.do_logout = True
            st.rerun()


def _card_start(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="q-settings-heading"><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)


def render(user_info: dict, selected: str | None = None) -> None:
    if st.session_state.get("show_signout_dialog"):
        _signout_dialog()

    username = user_info["username"]

    # Handle incoming OAuth callback if present in query params
    try:
        cb_result = oauth_connections.handle_callback(username)
        if cb_result and isinstance(cb_result, dict):
            p_name = cb_result.get("provider", "Account").title()
            st.success(f"Successfully connected {p_name}!")
            st.rerun()
    except Exception as exc:
        st.error(f"OAuth callback error: {exc}")

    try:
        profile = firebase_db.get_user_profile(username)
    except Exception:
        profile = dict(user_info)

    st.markdown('<div class="q-settings-title"><span>Account settings</span><small>Manage your profile and account</small></div>', unsafe_allow_html=True)
    if selected is None:
        selected = st.radio("Settings sections", _SECTIONS, key="settings_section", label_visibility="collapsed")
    _render_section(selected, username, user_info, profile)


def _render_section(selected: str, username: str, user_info: dict, profile: dict) -> None:

    if selected == "Profile":
        _card_start("Profile", "Your public identity inside QUEST.")
        avatar = profile.get("avatar")
        if avatar:
            st.markdown(f'<img class="q-avatar-large" src="{avatar}" alt="Profile avatar">', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="q-avatar-large q-avatar-placeholder">{profile.get("display_name", username)[:1].upper()}</div>', unsafe_allow_html=True)
        upload = st.file_uploader("Avatar", type=["png", "jpg", "jpeg", "webp"], key="avatar_upload")
        a1, a2 = st.columns(2)
        with a1:
            if upload and st.button("Replace avatar", key="replace_avatar", use_container_width=True):
                encoded = base64.b64encode(upload.getvalue()).decode("ascii")
                mime = upload.type or "image/png"
                avatar_data = f"data:{mime};base64,{encoded}"
                firebase_db.save_avatar(username, avatar_data)
                st.session_state.user_info["avatar"] = avatar_data
                st.success("Avatar updated.")
                st.rerun()
        with a2:
            if avatar and st.button("Delete avatar", key="delete_avatar", use_container_width=True):
                firebase_db.save_avatar(username, None)
                st.session_state.user_info.pop("avatar", None)
                st.success("Avatar removed.")
                st.rerun()

        with st.form("profile_form"):
            display_name = st.text_input("Display name", value=profile.get("display_name", user_info.get("display_name", username)))
            summary = st.text_area("Profile summary", value=profile.get("summary", ""), max_chars=240,
                                   placeholder="A short line about your investing style")
            if st.form_submit_button("Save profile", use_container_width=True):
                try:
                    ok, message = firebase_db.update_profile(username, display_name, summary)
                    if ok:
                        st.session_state.user_info["display_name"] = display_name.strip()
                        st.success(message)
                    else:
                        st.error(message)
                except Exception as exc:
                    st.error(f"Could not update profile: {exc}")

    elif selected == "Connections":
        _card_start("Connected Accounts", "Link your external accounts for public verification on QUEST.")

        st.markdown(
            """
            <div style="background: var(--q-surface-2); border: 1px solid var(--q-border); border-radius: var(--q-radius-sm, 10px); padding: 10px 14px; margin-top: 14px; margin-bottom: 16px; font-size: 0.85rem; color: var(--q-text-2);">
                <strong style="color: var(--q-text);">Public visibility:</strong> Connected accounts are visible to other QUEST users on your public profile.
            </div>
            """,
            unsafe_allow_html=True,
        )

        connections = oauth_connections.get_connections(username)

        active_providers = [
            {"id": "discord", "name": "Discord", "icon": "👾"},
            {"id": "google", "name": "Google", "icon": "🌐"},
            {"id": "linkedin", "name": "LinkedIn", "icon": "💼"},
        ]

        for p in active_providers:
            pid = p["id"]
            pname = p["name"]
            picon = p["icon"]
            is_connected = pid in connections
            conn = connections.get(pid, {})

            c1, c2 = st.columns([4, 1.3], vertical_alignment="center")
            with c1:
                if is_connected:
                    disp = conn.get("display_name") or conn.get("_discord_username") or "Connected"
                    st.markdown(
                        f"""
                        <div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--q-surface-2); border: 1px solid var(--q-border); border-radius: var(--q-radius-sm, 10px);">
                            <span style="font-size: 1.4rem;">{picon}</span>
                            <div style="flex: 1; min-width: 0;">
                                <div style="font-size: 0.95rem; font-weight: 500; color: var(--q-text);">{pname}</div>
                                <div style="font-size: 0.8rem; color: var(--q-text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{disp}</div>
                            </div>
                            <span style="background: var(--q-accent-weak); color: var(--q-accent); border: 1px solid var(--q-accent); font-size: 0.72rem; font-weight: 600; padding: 3px 8px; border-radius: 999px; letter-spacing: 0.3px;">Verified</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"""
                        <div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--q-surface-2); border: 1px solid var(--q-border); border-radius: var(--q-radius-sm, 10px);">
                            <span style="font-size: 1.4rem;">{picon}</span>
                            <div style="flex: 1; min-width: 0;">
                                <div style="font-size: 0.95rem; font-weight: 500; color: var(--q-text);">{pname}</div>
                                <div style="font-size: 0.8rem; color: var(--q-text-3);">Not connected</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            with c2:
                if is_connected:
                    if st.button("Disconnect", key=f"disconnect_{pid}", use_container_width=True):
                        oauth_connections.remove_connection(username, pid)
                        st.success(f"Disconnected {pname}.")
                        st.rerun()
                else:
                    try:
                        auth_url = oauth_connections.build_auth_url(pid, username)
                        st.link_button("Connect", auth_url, use_container_width=True)
                    except Exception as err:
                        st.button("Connect", key=f"disabled_conn_{pid}", disabled=True, use_container_width=True, help=str(err))

        st.markdown(
            """
            <div style="margin-top: 24px; margin-bottom: 10px; font-size: 0.75rem; font-weight: 600; color: var(--q-text-3); text-transform: uppercase; letter-spacing: 0.08em;">
                Coming Soon
            </div>
            """,
            unsafe_allow_html=True,
        )

        upcoming = [
            {"name": "WhatsApp", "icon": "💬", "desc": "Chat & portfolio alerts"},
            {"name": "Instagram", "icon": "📸", "desc": "Social badges & showcase"},
            {"name": "Groww", "icon": "📈", "desc": "Broker portfolio sync"},
            {"name": "Zerodha", "icon": "🪁", "desc": "Kite connect broker sync"},
        ]

        for up in upcoming:
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; margin-bottom: 8px; background: var(--q-surface-2); border: 1px solid var(--q-border); border-radius: var(--q-radius-sm, 10px); opacity: 0.6;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 1.2rem; filter: grayscale(1);">{up['icon']}</span>
                        <div>
                            <div style="font-size: 0.9rem; font-weight: 500; color: var(--q-text-2);">{up['name']}</div>
                            <div style="font-size: 0.75rem; color: var(--q-text-3);">{up['desc']}</div>
                        </div>
                    </div>
                    <span style="font-size: 0.72rem; color: var(--q-text-3); border: 1px solid var(--q-border-2); padding: 3px 8px; border-radius: 999px;">Coming soon</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    elif selected == "Theme":
        _card_start("Theme", "Choose the variant that feels right for your workspace.")

        # Per-row swatch colours via ::after — scoped and generated from all entries in VARIANT_LABELS.
        nth_rules = "\n".join(
            f"        #quest-theme-picker div[data-testid=\"stRadio\"] [role=\"radiogroup\"] > label:nth-of-type({i + 1})::after,\n"
            f"        div[data-testid=\"stElementContainer\"]:has(#quest-theme-picker) + div[data-testid=\"stElementContainer\"] div[data-testid=\"stRadio\"] [role=\"radiogroup\"] > label:nth-of-type({i + 1})::after {{ background: {swatch} !important; }}"
            for i, (_, _, swatch) in enumerate(ui_theme.VARIANT_LABELS)
        )
        st.markdown(
            f"""<style>
        /* Scoped to #quest-theme-picker only — will not affect sidebar or other radios */
        #quest-theme-picker,
        div:has(> #quest-theme-picker),
        div[data-testid="stElementContainer"]:has(#quest-theme-picker),
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] {{
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }}

        #quest-theme-picker div[data-testid="stRadio"],
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] div[data-testid="stRadio"] {{
            width: 100% !important;
            max-width: 100% !important;
            background: var(--q-surface-2) !important;
            border: 1px solid var(--q-border) !important;
            border-radius: var(--q-radius-lg, 16px) !important;
            padding: 16px !important;
            box-sizing: border-box !important;
            margin-top: 14px !important;
        }}
        #quest-theme-picker div[data-testid="stRadio"] > div,
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] div[data-testid="stRadio"] > div {{
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }}
        #quest-theme-picker div[data-testid="stRadio"] [role="radiogroup"],
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] div[data-testid="stRadio"] [role="radiogroup"] {{
            width: 100% !important;
            max-width: 100% !important;
            gap: 8px !important;
            display: flex !important;
            flex-direction: column !important;
            box-sizing: border-box !important;
        }}
        #quest-theme-picker div[data-testid="stRadio"] [role="radiogroup"] > label,
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] div[data-testid="stRadio"] [role="radiogroup"] > label {{
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            width: 100% !important;
            max-width: 100% !important;
            background: var(--q-surface) !important;
            border: 1px solid var(--q-border) !important;
            border-radius: 10px !important;
            padding: 10px 14px !important;
            box-sizing: border-box !important;
            cursor: pointer !important;
            margin: 0 !important;
            transition: all .16s var(--q-ease, ease) !important;
        }}
        #quest-theme-picker div[data-testid="stRadio"] [role="radiogroup"] > label:hover,
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] div[data-testid="stRadio"] [role="radiogroup"] > label:hover {{
            transform: translateY(-2px) !important;
            border-color: var(--q-border-2) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
        }}
        #quest-theme-picker div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked),
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {{
            border-color: var(--q-accent) !important;
        }}
        #quest-theme-picker div[data-testid="stRadio"] [role="radiogroup"] > label::after,
        div[data-testid="stElementContainer"]:has(#quest-theme-picker) + div[data-testid="stElementContainer"] div[data-testid="stRadio"] [role="radiogroup"] > label::after {{
            content: "" !important;
            display: inline-block !important;
            width: 16px !important;
            height: 16px !important;
            border-radius: 50% !important;
            border: 1px solid var(--q-border-2) !important;
            flex-shrink: 0 !important;
            margin-left: auto !important;
        }}
        /* Per-variant swatch colours */
{nth_rules}
</style>""",
            unsafe_allow_html=True,
        )

        keys     = [key   for key, _,     _ in ui_theme.VARIANT_LABELS]
        labels   = {key: label for key, label, _ in ui_theme.VARIANT_LABELS}
        curr_key = ui_theme.current_theme_variant()
        curr_idx = keys.index(curr_key) if curr_key in keys else 0

        st.markdown('<div id="quest-theme-picker">', unsafe_allow_html=True)
        chosen_key = st.radio(
            "Theme variant",
            options=keys,
            index=curr_idx,
            format_func=lambda k: labels[k],
            key="theme_variant_choice",
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        if chosen_key != curr_key:
            st.session_state.ui_variant = chosen_key
            st.rerun()

