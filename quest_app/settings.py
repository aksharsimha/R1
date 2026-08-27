import base64

import streamlit as st

import firebase_db
import ui_theme


_SECTIONS = ["Profile", "Theme", "Sign out"]


def _card_start(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="q-settings-heading"><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)


def render(user_info: dict, selected: str | None = None) -> None:
    username = user_info["username"]
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

    elif selected == "Theme":
        _card_start("Theme", "Choose the look that feels right for your workspace.")
        dark = st.radio("Colour mode", ["Dark", "Light"], index=0 if ui_theme.current_theme() == "dark" else 1,
                        horizontal=True, key="theme_choice")
        if (dark == "Dark") != (ui_theme.current_theme() == "dark"):
            st.session_state.ui_theme = "dark" if dark == "Dark" else "light"
            st.rerun()

    else:
        _card_start("Sign out", "End this QUEST session on this device.")
        if st.button("Sign out", type="primary", use_container_width=True):
            # We purposely do NOT call remove_remembered_account here.
            # This allows the account to stay in the multi-account cookie (so it appears in the Switcher).
            _preserve_keys = {"auth_cookie_override", "cookie_controller"}
            for key in list(st.session_state.keys()):
                if key not in _preserve_keys:
                    del st.session_state[key]
            st.query_params["page"] = "Overview"
            st.query_params.pop("return_to", None)
            st.session_state.do_logout = True
            st.query_params["logged_out"] = "true"
            st.rerun()
