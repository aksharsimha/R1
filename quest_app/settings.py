import base64
import html
import streamlit as st

import firebase_db
import ui_theme

_SECTIONS = ["Profile Customization", "Theme", "Sign out"]

_ACCENT_PRESETS = [
    ("#5DCAA5", "Teal"),
    ("#3B82F6", "Blue"),
    ("#6366F1", "Indigo"),
    ("#8B5CF6", "Violet"),
    ("#F59E0B", "Amber"),
    ("#64748B", "Slate"),
]

_FRAME_OPTIONS = [
    ("none", "None", "🚫"),
    ("gold", "Sovereign Gold", "🥇"),
    ("platinum", "Platinum Edge", "🥈"),
    ("emerald", "Emerald Prism", "💎"),
    ("sapphire", "Sapphire Frost", "🔵"),
    ("obsidian", "Obsidian Shadow", "⚫"),
]

_EFFECT_OPTIONS = [
    ("none", "None"),
    ("subtle_glow", "Subtle Glow"),
    ("gradient_border", "Gradient Border"),
    ("pulse_ring", "Pulse Ring"),
]

_THEME_OPTIONS = [
    ("default", "Default (Obsidian)"),
    ("midnight", "Midnight Capital"),
    ("aurora", "Aurora Equity"),
    ("charcoal", "Charcoal Terminal"),
    ("royal", "Royal Vault"),
]

_TYPOGRAPHY_OPTIONS = [
    ("Inter", "Inter (Clean Modern)"),
    ("JetBrains Mono", "JetBrains Mono (Quant Mono)"),
    ("Space Grotesk", "Space Grotesk (Neo-Fintech)"),
    ("DM Sans", "DM Sans (Geometric Editorial)"),
]

_BANNER_PRESETS = [
    ("gradient", "Default Gradient", ""),
    ("grid", "Fintech Matrix", "linear-gradient(135deg, rgba(15,23,42,0.9), rgba(30,41,59,0.9)), repeating-linear-gradient(0deg, transparent, transparent 19px, rgba(93,202,165,0.08) 20px), repeating-linear-gradient(90deg, transparent, transparent 19px, rgba(93,202,165,0.08) 20px)"),
    ("gold_bullion", "Gold Vault", "linear-gradient(135deg, #1c1508 0%, #382c13 50%, #151004 100%)"),
    ("aurora_night", "Aurora Market", "linear-gradient(135deg, #071a17 0%, #0d382f 50%, #031411 100%)"),
    ("deep_indigo", "Institutional Dark", "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0b0f19 100%)"),
]


def _card_start(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="q-settings-heading" style="margin-bottom: 20px;">'
        f'<h2 style="font-size: 1.5rem; font-weight: 700; color: var(--q-text); margin: 0 0 4px;">{title}</h2>'
        f'<p style="font-size: 0.88rem; color: var(--q-text-3); margin: 0;">{subtitle}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render(user_info: dict, selected: str | None = None) -> None:
    username = user_info.get("username", "")
    try:
        profile = firebase_db.get_user_profile(username)
    except Exception:
        profile = dict(user_info)

    st.markdown(
        '<div class="q-settings-title" style="margin-bottom: 24px;">'
        '<span style="font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px;">Account Settings</span>'
        '<br><small style="font-size: 0.88rem; color: var(--q-text-3);">Manage your profile, visual customization, and preferences</small>'
        '</div>',
        unsafe_allow_html=True,
    )

    if selected is None:
        selected = st.radio("Settings sections", _SECTIONS, key="settings_section", label_visibility="collapsed")

    # Map legacy section names if navigated from elsewhere
    if selected in ("Profile", "Customize", "Profile Customization"):
        _render_customization_section(username, user_info, profile)
    elif selected == "Theme":
        _render_theme_section()
    else:
        _render_signout_section()


def _render_customization_section(username: str, user_info: dict, profile: dict) -> None:
    _card_start("Profile Customization", "Personalize your public identity, avatar frames, banners, and visual theme.")

    # 1. Load saved customization or default
    try:
        saved_custom = firebase_db.get_profile_customization(username)
    except Exception:
        saved_custom = {
            "is_pro": False,
            "accent_color": "#5DCAA5",
            "banner_url": None,
            "avatar_frame": "none",
            "profile_effect": "none",
            "profile_theme": "default",
            "custom_status": "",
            "typography": "Inter",
            "show_pro_badge": True,
        }

    # 2. Initialize preview session state
    if "_customize_preview" not in st.session_state:
        st.session_state._customize_preview = {
            "is_pro": saved_custom.get("is_pro", False),
            "display_name": profile.get("display_name", user_info.get("display_name", username)),
            "summary": profile.get("summary", ""),
            "avatar": profile.get("avatar") or user_info.get("avatar"),
            "accent_color": saved_custom.get("accent_color", "#5DCAA5"),
            "banner_url": saved_custom.get("banner_url"),
            "avatar_frame": str(saved_custom.get("avatar_frame", "none")).lower(),
            "profile_effect": str(saved_custom.get("profile_effect", "none")).lower().replace(" ", "_"),
            "profile_theme": str(saved_custom.get("profile_theme", "default")).lower(),
            "custom_status": saved_custom.get("custom_status", ""),
            "typography": saved_custom.get("typography", "Inter"),
            "show_pro_badge": saved_custom.get("show_pro_badge", True),
        }

    prev = st.session_state._customize_preview
    is_pro = prev.get("is_pro", False)

    # Helper to show locked warning
    def _prompt_upgrade(feature_name: str = "This feature"):
        st.toast(f"🔒 {feature_name} is exclusive to QUEST PRO", icon="🔒")

    # Responsive two-column layout
    col_controls, col_preview = st.columns([3, 2], gap="large")

    with col_controls:
        # ─── FREE TIER: USER IDENTITY ───
        st.markdown(
            '<div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: var(--q-text-3); margin-bottom: 12px;">'
            '👤 User Identity <span style="font-size: 0.68rem; font-weight: 600; color: var(--q-accent); background: var(--q-accent-weak); padding: 1px 7px; border-radius: 4px; margin-left: 6px;">FREE</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        new_name = st.text_input(
            "Display Name",
            value=prev.get("display_name", username),
            placeholder="Your name or trader alias",
            key="custom_display_name_input",
            help="Your public name visible on leaderboards and the sidebar card",
        )
        if new_name != prev.get("display_name"):
            prev["display_name"] = new_name
            st.rerun()

        st.caption(f"Username: `@{username}` (immutable)")

        new_bio = st.text_area(
            "Bio / Investment Style",
            value=prev.get("summary", ""),
            max_chars=240,
            placeholder="e.g. Fundamental value investor focusing on NIFTY 50 and quant risk hedges.",
            key="custom_bio_input",
            help="A brief summary of your strategy and risk approach",
        )
        if new_bio != prev.get("summary"):
            prev["summary"] = new_bio
            st.rerun()

        # Avatar Picture Upload & Delete
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 12px 0 6px;">Profile Picture</div>',
            unsafe_allow_html=True,
        )
        avatar_file = st.file_uploader(
            "Upload avatar",
            type=["png", "jpg", "jpeg", "webp"],
            key="avatar_upload_input",
            label_visibility="collapsed",
        )
        av_col1, av_col2 = st.columns(2)
        with av_col1:
            if avatar_file and st.button("Apply New Avatar", key="btn_apply_avatar", use_container_width=True):
                encoded = base64.b64encode(avatar_file.getvalue()).decode("ascii")
                mime = avatar_file.type or "image/png"
                av_data = f"data:{mime};base64,{encoded}"
                prev["avatar"] = av_data
                st.toast("Avatar updated in preview! Click Save Changes to keep.", icon="✨")
                st.rerun()
        with av_col2:
            if prev.get("avatar") and st.button("Remove Avatar", key="btn_remove_avatar", use_container_width=True):
                prev["avatar"] = None
                st.toast("Avatar cleared in preview", icon="🗑️")
                st.rerun()

        # ─── FREE TIER: ACCENT COLOR PRESETS ───
        st.markdown(
            '<div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: var(--q-text-3); margin: 24px 0 10px;">'
            '🎨 Theme Accent Presets <span style="font-size: 0.68rem; font-weight: 600; color: var(--q-accent); background: var(--q-accent-weak); padding: 1px 7px; border-radius: 4px; margin-left: 6px;">FREE</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        swatch_cols = st.columns(len(_ACCENT_PRESETS))
        for idx, (hex_code, label) in enumerate(_ACCENT_PRESETS):
            with swatch_cols[idx]:
                is_active = (prev.get("accent_color", "#5DCAA5").upper() == hex_code.upper())
                if st.button(
                    f"{'✓ ' if is_active else ''}{label}",
                    key=f"swatch_btn_{idx}",
                    use_container_width=True,
                    help=f"Select {label} ({hex_code})",
                ):
                    prev["accent_color"] = hex_code
                    st.rerun()

        st.markdown("<hr style='border: none; border-top: 1px solid var(--q-border); margin: 28px 0 20px;'>", unsafe_allow_html=True)

        # ─── PRO MEMBERSHIP STATUS & DEMO TEST DRIVE ───
        st.markdown(
            '<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">'
            '<div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #D4A843;">'
            '⚡ PRO Personalization Tier'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Test Drive / Pro toggle card
        if is_pro:
            st.markdown(
                '<div style="background: linear-gradient(135deg, rgba(212,168,67,0.12), rgba(93,202,165,0.08)); border: 1px solid rgba(212,168,67,0.3); border-radius: 12px; padding: 14px 18px; margin-bottom: 20px;">'
                '<div style="font-size: 0.95rem; font-weight: 700; color: #D4A843;">👑 QUEST PRO Membership Active</div>'
                '<div style="font-size: 0.8rem; color: var(--q-text-2); margin-top: 2px;">All custom banners, avatar frames, effects, themes, and badges are unlocked.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Switch to Free Mode Preview", key="toggle_pro_off", help="View how the UI appears for free users"):
                prev["is_pro"] = False
                st.toast("Switched to Free preview mode", icon="ℹ️")
                st.rerun()
        else:
            st.markdown(
                '<div style="background: var(--q-surface-2); border: 1px solid var(--q-border); border-radius: 12px; padding: 14px 18px; margin-bottom: 20px;">'
                '<div style="font-size: 0.95rem; font-weight: 700; color: var(--q-text);">'
                'Free Plan Active <span style="font-size: 0.68rem; font-weight: 700; color: #D4A843; background: rgba(212,168,67,0.12); padding: 2px 7px; border-radius: 4px; margin-left: 6px;">🔒 PRO FEATURES LOCKED</span>'
                '</div>'
                '<div style="font-size: 0.8rem; color: var(--q-text-3); margin-top: 2px;">'
                'Bespoke banners, metallic avatar frames, and custom themes require PRO.'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("👑 Test Drive PRO Features (Free Live Demo)", key="toggle_pro_on", use_container_width=True, type="primary"):
                prev["is_pro"] = True
                st.toast("👑 PRO Unlocked for live preview! Try all features.", icon="🎉")
                st.rerun()

        # ─── PRO FEATURE 1: PROFILE BANNER ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 16px 0 6px;">'
            'Custom Profile Banner <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        banner_file = st.file_uploader(
            "Upload banner",
            type=["png", "jpg", "jpeg", "webp"],
            key="custom_banner_uploader",
            label_visibility="collapsed",
            disabled=not is_pro,
            help="Upload an image up to 300KB to display at the top of your profile card",
        )
        if banner_file:
            if not is_pro:
                _prompt_upgrade("Custom Profile Banner")
            elif banner_file.size > 300000:
                st.error("Banner image must be under 300KB.")
            else:
                encoded_banner = base64.b64encode(banner_file.getvalue()).decode("ascii")
                mime_b = banner_file.type or "image/png"
                prev["banner_url"] = f"data:{mime_b};base64,{encoded_banner}"
                st.toast("Banner applied to live preview!", icon="🖼️")
                st.rerun()

        # Preset Banners
        banner_cols = st.columns(len(_BANNER_PRESETS))
        for b_idx, (b_id, b_label, b_css) in enumerate(_BANNER_PRESETS):
            with banner_cols[b_idx]:
                if st.button(b_label, key=f"btn_banner_preset_{b_idx}", use_container_width=True, disabled=not is_pro):
                    if not is_pro:
                        _prompt_upgrade("Preset Banners")
                    else:
                        prev["banner_url"] = b_css if b_css else None
                        st.rerun()

        # ─── PRO FEATURE 2: AVATAR FRAMES ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 20px 0 8px;">'
            'Premium Avatar Frames <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        frame_cols = st.columns(3)
        for f_idx, (f_val, f_name, f_icon) in enumerate(_FRAME_OPTIONS):
            col_target = frame_cols[f_idx % 3]
            with col_target:
                is_selected = (prev.get("avatar_frame", "none") == f_val)
                frame_label = f"{f_icon} {f_name}" if not is_selected else f"✓ {f_icon} {f_name}"
                if st.button(frame_label, key=f"btn_frame_{f_val}", use_container_width=True, disabled=not is_pro):
                    if not is_pro:
                        _prompt_upgrade("Avatar Frames")
                    else:
                        prev["avatar_frame"] = f_val
                        st.rerun()

        # ─── PRO FEATURE 3: CUSTOM ACCENT COLOR ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 20px 0 6px;">'
            'Custom Accent Color <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        custom_hex = st.color_picker(
            "Select custom hex",
            value=prev.get("accent_color", "#5DCAA5"),
            key="custom_hex_picker",
            label_visibility="collapsed",
            disabled=not is_pro,
        )
        if custom_hex != prev.get("accent_color"):
            if not is_pro:
                _prompt_upgrade("Custom Hex Picker")
            else:
                prev["accent_color"] = custom_hex
                st.rerun()

        # ─── PRO FEATURE 4: PROFILE EFFECT ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 20px 0 6px;">'
            'Profile Effect & Ambient Glow <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        current_eff = prev.get("profile_effect", "none")
        eff_keys = [k for k, v in _EFFECT_OPTIONS]
        eff_index = eff_keys.index(current_eff) if current_eff in eff_keys else 0
        chosen_eff = st.selectbox(
            "Profile Effect",
            eff_keys,
            format_func=lambda k: dict(_EFFECT_OPTIONS).get(k, k),
            index=eff_index,
            key="custom_eff_select",
            label_visibility="collapsed",
            disabled=not is_pro,
        )
        if chosen_eff != current_eff:
            if not is_pro:
                _prompt_upgrade("Profile Effects")
            else:
                prev["profile_effect"] = chosen_eff
                st.rerun()

        # ─── PRO FEATURE 5: PROFILE THEME ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 20px 0 6px;">'
            'Profile Theme <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        current_thm = prev.get("profile_theme", "default")
        thm_keys = [k for k, v in _THEME_OPTIONS]
        thm_index = thm_keys.index(current_thm) if current_thm in thm_keys else 0
        chosen_thm = st.selectbox(
            "Profile Theme",
            thm_keys,
            format_func=lambda k: dict(_THEME_OPTIONS).get(k, k),
            index=thm_index,
            key="custom_thm_select",
            label_visibility="collapsed",
            disabled=not is_pro,
        )
        if chosen_thm != current_thm:
            if not is_pro:
                _prompt_upgrade("Profile Themes")
            else:
                prev["profile_theme"] = chosen_thm
                st.rerun()

        # ─── PRO FEATURE 6: CUSTOM STATUS ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 20px 0 6px;">'
            'Custom Investor Status <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        new_status = st.text_input(
            "Custom Status",
            value=prev.get("custom_status", ""),
            max_chars=50,
            placeholder="📈 Bullish on NIFTY 50 | Long Alpha",
            key="custom_status_input",
            label_visibility="collapsed",
            disabled=not is_pro,
        )
        if new_status != prev.get("custom_status"):
            if not is_pro:
                _prompt_upgrade("Custom Status")
            else:
                prev["custom_status"] = new_status
                st.rerun()

        # ─── PRO FEATURE 7: TYPOGRAPHY ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 20px 0 6px;">'
            'Profile Typography <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        current_typo = prev.get("typography", "Inter")
        typo_keys = [k for k, v in _TYPOGRAPHY_OPTIONS]
        typo_index = typo_keys.index(current_typo) if current_typo in typo_keys else 0
        chosen_typo = st.selectbox(
            "Profile Typography",
            typo_keys,
            format_func=lambda k: dict(_TYPOGRAPHY_OPTIONS).get(k, k),
            index=typo_index,
            key="custom_typo_select",
            label_visibility="collapsed",
            disabled=not is_pro,
        )
        if chosen_typo != current_typo:
            if not is_pro:
                _prompt_upgrade("Typography Options")
            else:
                prev["typography"] = chosen_typo
                st.rerun()

        # ─── PRO FEATURE 8: PRO BADGE TOGGLE ───
        st.markdown(
            '<div style="font-size: 0.85rem; font-weight: 600; color: var(--q-text); margin: 20px 0 6px;">'
            'Badge Display <span class="q-locked-label">🔒 PRO</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        show_badge_val = st.checkbox(
            "Display '⚡ PRO' verification badge on profile & sidebar",
            value=prev.get("show_pro_badge", True),
            key="custom_badge_checkbox",
            disabled=not is_pro,
        )
        if show_badge_val != prev.get("show_pro_badge"):
            if not is_pro:
                _prompt_upgrade("PRO Badge")
            else:
                prev["show_pro_badge"] = show_badge_val
                st.rerun()

        # ─── UPGRADE TO PRO CTA CARD ───
        if not is_pro:
            st.markdown(
                """
                <div class="q-upgrade-card" style="margin-top: 24px;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <span style="font-size: 1.15rem; font-weight: 700; color: #D4A843; letter-spacing: -0.3px;">
                            ⚡ Unlock QUEST PRO
                        </span>
                        <span style="font-size: 0.82rem; font-weight: 600; color: #D4A843; background: rgba(212,168,67,0.15); padding: 2px 8px; border-radius: 6px;">
                            ₹199 / month
                        </span>
                    </div>
                    <div style="font-size: 0.82rem; color: var(--q-text-2); margin: 10px 0 14px; line-height: 1.5;">
                        Elevate your risk terminal identity with bespoke banners, metallic avatar frames, unconstrained color palettes, custom investor statuses, and executive profile effects.
                    </div>
                    <div style="font-size: 0.74rem; color: var(--q-text-3); margin-bottom: 14px;">
                        ✓ Instant activation &nbsp;·&nbsp; ✓ Cancel anytime &nbsp;·&nbsp; ✓ Institutional priority updates
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("⚡ Upgrade to PRO — ₹199/month", key="btn_upgrade_cta", type="primary", use_container_width=True):
                st.info("💳 Secure checkout integration is being initialized! Click 'Test Drive PRO Features' above to demo all features now.")

        # ─── ACTION BUTTONS: SAVE & RESET ───
        st.markdown("<hr style='border: none; border-top: 1px solid var(--q-border); margin: 28px 0 16px;'>", unsafe_allow_html=True)
        act_col1, act_col2 = st.columns(2)
        with act_col1:
            if st.button("💾 Save Changes", key="btn_save_customization", type="primary", use_container_width=True):
                # 1. Update basic profile info
                disp = prev.get("display_name", username).strip() or username
                summ = prev.get("summary", "")
                try:
                    firebase_db.update_profile(username, disp, summ)
                    st.session_state.user_info["display_name"] = disp
                except Exception as e:
                    print(f"Error updating profile: {e}")

                # 2. Update avatar if changed
                av = prev.get("avatar")
                try:
                    firebase_db.save_avatar(username, av)
                    if av:
                        st.session_state.user_info["avatar"] = av
                    else:
                        st.session_state.user_info.pop("avatar", None)
                except Exception as e:
                    print(f"Error saving avatar: {e}")

                # 3. Save customization settings
                clean_custom = {
                    "is_pro": prev.get("is_pro", False),
                    "accent_color": prev.get("accent_color", "#5DCAA5"),
                    "banner_url": prev.get("banner_url"),
                    "avatar_frame": prev.get("avatar_frame", "none"),
                    "profile_effect": prev.get("profile_effect", "none"),
                    "profile_theme": prev.get("profile_theme", "default"),
                    "custom_status": prev.get("custom_status", ""),
                    "typography": prev.get("typography", "Inter"),
                    "show_pro_badge": prev.get("show_pro_badge", True),
                }
                ok = firebase_db.save_profile_customization(username, clean_custom)
                if ok:
                    st.success("✅ Profile customization saved successfully! Refresh or switch pages to see your updated profile.")
                    st.balloons()
                else:
                    st.error("Failed to save customization settings. Please try again.")

        with act_col2:
            if st.button("↩ Reset to Default", key="btn_reset_customization", use_container_width=True):
                st.session_state._customize_preview = {
                    "is_pro": False,
                    "display_name": profile.get("display_name", username),
                    "summary": profile.get("summary", ""),
                    "avatar": profile.get("avatar"),
                    "accent_color": "#5DCAA5",
                    "banner_url": None,
                    "avatar_frame": "none",
                    "profile_effect": "none",
                    "profile_theme": "default",
                    "custom_status": "",
                    "typography": "Inter",
                    "show_pro_badge": True,
                }
                st.toast("Profile preview reset to defaults.", icon="↩️")
                st.rerun()

    # ─── RIGHT COLUMN: LIVE PROFILE PREVIEW CARD ───
    with col_preview:
        st.markdown(
            '<div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: var(--q-text-3); margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">'
            '<span>Live Profile Preview</span>'
            '<span style="font-size: 0.7rem; font-weight: 500; color: var(--q-accent);">● Real-Time Sync</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        accent = prev.get("accent_color", "#5DCAA5")
        user_disp = html.escape(prev.get("display_name") or username)
        user_bio = html.escape(prev.get("summary") or "No investment style summary provided yet.")
        user_status = html.escape(prev.get("custom_status") or "")

        # Banner style
        custom_b = prev.get("banner_url")
        if custom_b:
            if custom_b.startswith("data:") or custom_b.startswith("http"):
                banner_style = f"background: url('{custom_b}') center/cover no-repeat;"
            else:
                banner_style = f"background: {custom_b};"
        else:
            banner_style = f"background: linear-gradient(135deg, {accent} 0%, rgba(15,23,42,0.85) 100%);"

        # Avatar Frame Class
        raw_f = str(prev.get("avatar_frame", "none")).lower()
        frame_cls = f"q-frame-{raw_f}" if raw_f not in ("none", "", "null") else ""

        # Profile Effect Class
        raw_e = str(prev.get("profile_effect", "none")).lower().replace(" ", "_")
        effect_cls = ""
        if raw_e == "subtle_glow":
            effect_cls = "q-effect-glow"
        elif raw_e == "gradient_border":
            effect_cls = "q-effect-gradient"
        elif raw_e == "pulse_ring":
            effect_cls = "q-effect-pulse"

        # Theme Class
        raw_t = str(prev.get("profile_theme", "default")).lower()
        theme_cls = f"q-theme-{raw_t}" if raw_t in ("midnight", "aurora", "charcoal", "royal") else ""

        # Font family
        font_family = prev.get("typography", "Inter")

        # Avatar rendering
        av_src = prev.get("avatar")
        if av_src:
            av_html = f'<img src="{av_src}" alt="Avatar" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">'
        else:
            initial = user_disp[:1].upper() if user_disp else "U"
            av_html = f'<span style="font-size:1.6rem; font-weight:700; color:var(--q-text);">{initial}</span>'

        # Badge rendering
        badge_html = '<span class="q-pro-badge">PRO</span>' if (is_pro and prev.get("show_pro_badge", True)) else ""

        # Status rendering
        status_html = (
            f'<div style="font-size:0.75rem; color:var(--q-text-2); margin-top:4px; display:flex; align-items:center; gap:4px;">'
            f'<span>{user_status}</span>'
            f'</div>'
        ) if user_status else ""

        # Construct self-contained preview card HTML
        preview_card_html = f"""
        <div style="position: sticky; top: 1rem;">
            <div class="q-profile-preview-card {theme_cls} {effect_cls}" style="
                background: var(--q-surface);
                border: 1px solid var(--q-border);
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                font-family: '{font_family}', sans-serif;
                transition: all 0.3s var(--q-ease);
                --user-accent: {accent};
            ">
                <!-- Banner -->
                <div style="height: 120px; {banner_style} position: relative;">
                    {f'<div style="position: absolute; top: 10px; right: 12px;">{badge_html}</div>' if badge_html else ''}
                </div>

                <!-- Avatar & Identity Bar -->
                <div style="padding: 0 20px 20px; margin-top: -40px; position: relative;">
                    <div class="{frame_cls}" style="
                        width: 74px;
                        height: 74px;
                        border-radius: 50%;
                        background: var(--q-surface-2);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 4px 14px rgba(0,0,0,0.35);
                        border: 3px solid var(--q-surface);
                        overflow: hidden;
                        margin-bottom: 12px;
                    ">
                        {av_html}
                    </div>

                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="font-size: 1.15rem; font-weight: 700; color: var(--q-text); letter-spacing: -0.3px;">
                            {user_disp}
                        </span>
                        {badge_html}
                    </div>

                    <div style="font-size: 0.8rem; color: var(--q-text-3); font-family: 'JetBrains Mono', monospace;">
                        @{username}
                    </div>

                    {status_html}

                    <div style="
                        font-size: 0.82rem;
                        color: var(--q-text-2);
                        line-height: 1.45;
                        margin: 12px 0 16px;
                        padding: 10px 12px;
                        background: var(--q-surface-2);
                        border-radius: 8px;
                        border-left: 3px solid {accent};
                    ">
                        {user_bio}
                    </div>

                    <!-- Fintech Badges Row -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px;">
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--q-border); border-radius: 8px; padding: 8px 10px;">
                            <div style="font-size: 0.65rem; color: var(--q-text-3); text-transform: uppercase; font-weight: 600;">Risk Rating</div>
                            <div style="font-size: 0.88rem; font-weight: 700; color: {accent};">Moderate Growth</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--q-border); border-radius: 8px; padding: 8px 10px;">
                            <div style="font-size: 0.65rem; color: var(--q-text-3); text-transform: uppercase; font-weight: 600;">Terminal Tier</div>
                            <div style="font-size: 0.88rem; font-weight: 700; color: {'#D4A843' if is_pro else 'var(--q-text)'};">
                                {'⚡ QUEST PRO' if is_pro else 'Standard'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div style="text-align: center; margin-top: 12px; font-size: 0.75rem; color: var(--q-text-3);">
                Preview updates instantly as you adjust options.
            </div>
        </div>
        """
        st.markdown(preview_card_html, unsafe_allow_html=True)


def _render_theme_section() -> None:
    _card_start("Theme", "Choose the visual appearance that feels right for your trading workspace.")
    dark = st.radio(
        "Colour mode",
        ["Dark", "Light"],
        index=0 if ui_theme.current_theme() == "dark" else 1,
        horizontal=True,
        key="theme_choice",
    )
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
