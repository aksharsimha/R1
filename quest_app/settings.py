import base64

import streamlit as st

import firebase_db
import ui_theme


_SECTIONS = ["Profile", "Customize", "Theme", "Sign out"]


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

    elif selected == "Customize":
        _card_start("Customize Profile", "Personalize your QUEST identity.")
        
        try:
            customization = firebase_db.get_profile_customization(username)
        except Exception:
            customization = {
                "is_pro": False,
                "accent_color": "#5DCAA5",
                "banner_url": "",
                "avatar_frame": "None",
                "profile_effect": "None",
                "profile_theme": "Default",
                "custom_status": "",
                "typography": "Inter",
                "show_pro_badge": False
            }
        
        if "_customize_preview" not in st.session_state:
            st.session_state._customize_preview = customization.copy()

        preview = st.session_state._customize_preview
        is_pro = preview.get("is_pro", False)
        
        def require_pro(key_name, new_value, is_pro):
            if not is_pro:
                st.toast("🔒 This feature requires QUEST PRO", icon="🔒")
            else:
                st.session_state._customize_preview[key_name] = new_value
                
        def update_preview(key_name, new_value):
            st.session_state._customize_preview[key_name] = new_value

        col_controls, col_preview = st.columns([3, 2])
        
        with col_controls:
            st.markdown("### Accent Color")
            colors = ["#5DCAA5", "#6366F1", "#8B5CF6", "#F59E0B", "#EF4444", "#64748B"]
            color_cols = st.columns(6)
            for i, color in enumerate(colors):
                with color_cols[i]:
                    if st.button("", key=f"color_btn_{i}", help=color):
                        update_preview("accent_color", color)
                        st.rerun()
                    st.markdown(f'<div style="background-color: {color}; width: 100%; height: 30px; border-radius: 50%; margin-top: -45px; pointer-events: none;"></div>', unsafe_allow_html=True)
            
            st.markdown("### 🔒 PRO Profile Banner" if not is_pro else "### Profile Banner")
            banner_upload = st.file_uploader("Banner Image (Max 200KB)", type=["png", "jpg", "webp"], disabled=not is_pro)
            if banner_upload and is_pro:
                if banner_upload.size <= 200000:
                    encoded = base64.b64encode(banner_upload.getvalue()).decode("ascii")
                    mime = banner_upload.type or "image/png"
                    update_preview("banner_url", f"data:{mime};base64,{encoded}")
                    st.rerun()
                else:
                    st.error("Image too large. Max 200KB.")
            elif banner_upload and not is_pro:
                st.toast("🔒 This feature requires QUEST PRO", icon="🔒")

            st.markdown("### 🔒 PRO Avatar Frame" if not is_pro else "### Avatar Frame")
            frame_options = [("None", "🚫"), ("Gold", "🥇"), ("Platinum", "🥈"), ("Emerald", "💎"), ("Sapphire", "🔵"), ("Obsidian", "⚫")]
            frame_cols = st.columns(len(frame_options))
            for i, (f_name, f_emoji) in enumerate(frame_options):
                with frame_cols[i]:
                    if st.button(f_emoji, key=f"frame_{f_name}"):
                        if is_pro:
                            update_preview("avatar_frame", f_name)
                            st.rerun()
                        else:
                            st.toast("🔒 This feature requires QUEST PRO", icon="🔒")
                    st.caption(f_name)

            st.markdown("### 🔒 PRO Custom Accent" if not is_pro else "### Custom Accent")
            custom_color = st.color_picker("Pick a color", value=preview.get("accent_color", "#5DCAA5"), disabled=not is_pro)
            if custom_color != preview.get("accent_color") and is_pro:
                update_preview("accent_color", custom_color)
                st.rerun()
            elif custom_color != preview.get("accent_color") and not is_pro:
                st.toast("🔒 This feature requires QUEST PRO", icon="🔒")

            st.markdown("### 🔒 PRO Profile Effect" if not is_pro else "### Profile Effect")
            effects = ["None", "Subtle Glow", "Gradient Border", "Pulse Ring"]
            effect = st.selectbox("Effect", effects, index=effects.index(preview.get("profile_effect", "None")), disabled=not is_pro, label_visibility="collapsed")
            if effect != preview.get("profile_effect"):
                if is_pro:
                    update_preview("profile_effect", effect)
                    st.rerun()
                else:
                    st.toast("🔒 This feature requires QUEST PRO", icon="🔒")

            st.markdown("### 🔒 PRO Profile Theme" if not is_pro else "### Profile Theme")
            themes = ["Default", "Midnight", "Aurora", "Charcoal", "Royal"]
            theme = st.selectbox("Theme", themes, index=themes.index(preview.get("profile_theme", "Default")), disabled=not is_pro, label_visibility="collapsed")
            if theme != preview.get("profile_theme"):
                if is_pro:
                    update_preview("profile_theme", theme)
                    st.rerun()
                else:
                    st.toast("🔒 This feature requires QUEST PRO", icon="🔒")

            st.markdown("### 🔒 PRO Custom Status" if not is_pro else "### Custom Status")
            status = st.text_input("Status", value=preview.get("custom_status", ""), max_chars=50, placeholder="📈 Bullish on NIFTY", disabled=not is_pro, label_visibility="collapsed")
            if status != preview.get("custom_status"):
                if is_pro:
                    update_preview("custom_status", status)
                else:
                    st.toast("🔒 This feature requires QUEST PRO", icon="🔒")

            st.markdown("### 🔒 PRO Typography" if not is_pro else "### Typography")
            fonts = ["Inter", "JetBrains Mono", "Space Grotesk", "DM Sans"]
            font = st.selectbox("Typography", fonts, index=fonts.index(preview.get("typography", "Inter")), disabled=not is_pro, label_visibility="collapsed")
            if font != preview.get("typography"):
                if is_pro:
                    update_preview("typography", font)
                    st.rerun()
                else:
                    st.toast("🔒 This feature requires QUEST PRO", icon="🔒")

            st.markdown("### 🔒 PRO Show PRO Badge" if not is_pro else "### Show PRO Badge")
            show_badge = st.checkbox("Show PRO badge on profile", value=preview.get("show_pro_badge", False), disabled=not is_pro)
            if show_badge != preview.get("show_pro_badge"):
                if is_pro:
                    update_preview("show_pro_badge", show_badge)
                    st.rerun()
                else:
                    st.toast("🔒 This feature requires QUEST PRO", icon="🔒")

            st.write("")
            if not is_pro:
                st.markdown("""
                <div class="q-upgrade-card" style="background: var(--q-surface-2); padding: 16px; border-radius: 12px; border: 1px solid var(--q-border); margin-bottom: 16px;">
                    <div style="font-size:1.3rem;font-weight:700;color:#D4A843;">⚡ Unlock QUEST PRO</div>
                    <div style="font-size:0.85rem;color:var(--q-text-2);margin:8px 0 14px;">Premium profile customization, custom banners, avatar frames, and exclusive profile effects.</div>
                    <div style="font-size:0.78rem;color:var(--q-text-3);margin-bottom:10px;">₹199/month · Cancel anytime</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("⚡ Upgrade to PRO", use_container_width=True):
                    st.info("PRO subscriptions coming soon! Stay tuned.")
            
            btn1, btn2 = st.columns(2)
            with btn1:
                if st.button("💾 Save Changes", use_container_width=True):
                    firebase_db.save_profile_customization(username, st.session_state._customize_preview)
                    st.success("Profile customization saved.")
            with btn2:
                if st.button("↩ Reset to Default", use_container_width=True):
                    st.session_state._customize_preview = customization.copy()
                    st.rerun()

        with col_preview:
            accent = preview.get("accent_color", "#5DCAA5")
            banner_bg = f"url('{preview['banner_url']}') center/cover" if preview.get("banner_url") else f"linear-gradient(135deg, {accent}, rgba(0,0,0,0.3))"
            
            theme_class = ""
            if preview.get("profile_theme") == "Midnight": theme_class = "q-theme-midnight"
            elif preview.get("profile_theme") == "Aurora": theme_class = "q-theme-aurora"
            elif preview.get("profile_theme") == "Charcoal": theme_class = "q-theme-charcoal"
            elif preview.get("profile_theme") == "Royal": theme_class = "q-theme-royal"
            
            effect_class = ""
            if preview.get("profile_effect") == "Subtle Glow": effect_class = "q-effect-glow"
            elif preview.get("profile_effect") == "Gradient Border": effect_class = "q-effect-gradient"
            elif preview.get("profile_effect") == "Pulse Ring": effect_class = "q-effect-pulse"
            
            frame_class = ""
            if preview.get("avatar_frame") == "Gold": frame_class = "q-frame-gold"
            elif preview.get("avatar_frame") == "Platinum": frame_class = "q-frame-platinum"
            elif preview.get("avatar_frame") == "Emerald": frame_class = "q-frame-emerald"
            elif preview.get("avatar_frame") == "Sapphire": frame_class = "q-frame-sapphire"
            elif preview.get("avatar_frame") == "Obsidian": frame_class = "q-frame-obsidian"
            
            display_name = profile.get("display_name", user_info.get("display_name", username))
            bio = profile.get("summary", "")
            
            pro_badge = '<span class="q-pro-badge">PRO</span>' if preview.get("show_pro_badge") and is_pro else ""
            
            avatar = profile.get("avatar")
            if avatar:
                avatar_img = f'<img src="{avatar}" alt="Avatar">'
            else:
                avatar_img = f'<div style="font-size: 24px; font-weight: bold; color: var(--q-text);">{display_name[:1].upper()}</div>'
                
            status_line = ""
            if preview.get("custom_status"):
                status_line = f'<div style="font-size: 0.8rem; margin-top: 6px; font-style: italic; color: var(--q-text-2);">{preview["custom_status"]}</div>'

            html = f"""
            <style>
            .q-profile-preview {{
                background: var(--q-surface); border: 1px solid var(--q-border); border-radius: 16px; overflow: hidden; max-width: 320px; margin: 0 auto;
                font-family: {preview.get("typography", "Inter")}, sans-serif;
            }}
            .q-preview-banner {{ height: 100px; background: {banner_bg}; background-size: cover; background-position: center; position: relative; padding: 8px; text-align: right; }}
            .q-preview-avatar-wrap {{ margin-top: -32px; padding: 0 16px; position: relative; z-index: 1; }}
            .q-preview-avatar {{ width: 64px; height: 64px; border-radius: 50%; background: var(--q-surface-2); border: 3px solid var(--q-surface); display: flex; align-items: center; justify-content: center; overflow: hidden; }}
            .q-preview-avatar img {{ width: 100%; height: 100%; object-fit: cover; }}
            .q-preview-info {{ padding: 8px 16px 16px; }}
            .q-preview-name {{ font-weight: 700; font-size: 1.05rem; color: var(--q-text); display: flex; align-items: center; }}
            .q-preview-username {{ font-size: 0.8rem; color: var(--q-text-3); }}
            .q-preview-bio {{ font-size: 0.82rem; color: var(--q-text-2); margin-top: 8px; line-height: 1.4; }}
            .q-pro-badge {{ font-size: 0.6rem; background: linear-gradient(135deg, #D4A843, #C0984D); padding: 1px 6px; border-radius: 4px; color: #fff; font-weight: 700; margin-left: 6px; vertical-align: middle; }}
            
            .q-frame-gold {{ border: 2.5px solid #D4A843; box-shadow: 0 0 12px rgba(212,168,67,0.35); }}
            .q-frame-platinum {{ border: 2.5px solid #A8B4C0; box-shadow: 0 0 12px rgba(168,180,192,0.35); }}
            .q-frame-emerald {{ border: 2.5px solid #10B981; box-shadow: 0 0 12px rgba(16,185,129,0.35); }}
            .q-frame-sapphire {{ border: 2.5px solid #3B82F6; box-shadow: 0 0 12px rgba(59,130,246,0.35); }}
            .q-frame-obsidian {{ border: 2.5px solid #6B7280; box-shadow: 0 0 12px rgba(107,114,128,0.35), inset 0 0 6px rgba(0,0,0,0.5); }}
            
            .q-effect-glow {{ box-shadow: 0 0 25px rgba(93,202,165, 0.15); }}
            .q-effect-gradient {{ border-image: linear-gradient(135deg, {accent}, #8B5CF6) 1; border-width: 2px; border-style: solid; }}
            
            @keyframes q-pulse {{
                0%,100% {{ box-shadow: 0 0 0 0 rgba(93,202,165,0.2); }}
                50% {{ box-shadow: 0 0 15px 4px rgba(93,202,165,0.15); }}
            }}
            .q-effect-pulse {{ animation: q-pulse 2s infinite; }}
            
            .q-theme-midnight {{ background: linear-gradient(180deg, #0c0e1a 0%, #151929 100%); border-color: rgba(99,102,241,0.3); }}
            .q-theme-aurora {{ background: linear-gradient(180deg, #0a1628 0%, #132a1e 100%); border-color: rgba(16,185,129,0.3); }}
            .q-theme-charcoal {{ background: linear-gradient(180deg, #1a1a1a 0%, #2d2d2d 100%); border-color: rgba(255,255,255,0.1); }}
            .q-theme-royal {{ background: linear-gradient(180deg, #1a0f2e 0%, #2d1b4e 100%); border-color: rgba(139,92,246,0.3); }}
            </style>
            
            <div class="q-profile-preview {theme_class} {effect_class}" style="--user-accent: {accent};">
                <div class="q-preview-banner">
                    {pro_badge}
                </div>
                <div class="q-preview-avatar-wrap">
                    <div class="q-preview-avatar {frame_class}">
                        {avatar_img}
                    </div>
                </div>
                <div class="q-preview-info">
                    <div class="q-preview-name">{display_name} {pro_badge}</div>
                    <div class="q-preview-username">@{username}</div>
                    {status_line}
                    <div class="q-preview-bio">{bio}</div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

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
            st.rerun()
