import base64

import streamlit as st

import firebase_db
import ui_theme


_SECTIONS = ["Profile", "Theme"]


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

        if dark == "Dark":
            variants = ["Classic", "Midnight", "Void", "Graphite", "Plum", "Ash", "Jade"]
            curr_variant = ui_theme.current_dark_variant().title()
            idx = variants.index(curr_variant) if curr_variant in variants else 0
            dark_variant = st.selectbox("Dark theme", variants, index=idx, key="dark_variant_choice")
            if dark_variant.lower() != ui_theme.current_dark_variant():
                st.session_state.ui_dark_variant = dark_variant.lower()
                st.rerun()
