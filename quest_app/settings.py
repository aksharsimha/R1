import base64
import html
import urllib.parse
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


# Discord-inspired premium card themes (Premium Tier)
_PREMIUM_THEMES = [
    ("default", "Classic Dark", "#111214", "#5865F2"),
    ("loki_violet", "Velvet Violet (Loki)", "#201138", "#A855F7"),
    ("matrix_slate", "Midnight Matrix", "#0B0F19", "#06B6D4"),
    ("cyber_neon", "Cyberpunk Neon", "#1A0B2E", "#F43F5E"),
    ("emerald_vault", "Emerald Vault", "#071B16", "#10B981"),
    ("gold_prestige", "Sovereign Gold", "#1C1608", "#EAB308"),
]

_ANIMATION_OPTIONS = [
    ("none", "None (Static Cyberpunk)", "Clean circuit traces with static neon border"),
    ("neon_border", "⚡ Cyber Neon Pulse", "Breathing luminous neon boundary with ambient edge glow"),
    ("holo_scanline", "📡 Holographic Scanline", "Sweeping horizontal laser beam scanning vertically"),
    ("circuit_surge", "🔮 Circuit Energy Surge", "Rhythmic electric power surges flashing across motherboard traces"),
    ("rgb_orbit", "🌈 Prism Chroma Stream", "Flowing rainbow RGB prismatic light orbiting the card boundary"),
    ("glitch_aura", "⚡ Cyber Glitch Aura", "Dynamic chromatic aberration dual-shadow pulsing"),
]



def _build_cyber_circuit_svg(theme_color: str = "#a855f7", cyan_accent: str = "#38bdf8") -> str:
    """Generate high-tech motherboard circuit traces SVG pattern for the profile card."""
    safe_theme = theme_color if isinstance(theme_color, str) and theme_color.startswith("#") else "#a855f7"
    safe_cyan = cyan_accent if isinstance(cyan_accent, str) and cyan_accent.startswith("#") else "#38bdf8"
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='400' height='600' viewBox='0 0 400 600' fill='none'>
      <defs>
        <pattern id='p_grid' width='24' height='24' patternUnits='userSpaceOnUse'>
          <path d='M 24 0 L 0 0 0 24' fill='none' stroke='{safe_theme}' stroke-width='0.5' stroke-opacity='0.12'/>
        </pattern>
      </defs>
      <rect width='400' height='600' fill='url(#p_grid)'/>
      
      <!-- Microchips / Processors -->
      <rect x='250' y='180' width='100' height='80' rx='5' fill='#05060a' fill-opacity='0.8' stroke='{safe_theme}' stroke-width='1.5' stroke-opacity='0.45'/>
      <rect x='258' y='188' width='84' height='64' rx='3' fill='none' stroke='{safe_cyan}' stroke-width='1' stroke-opacity='0.3'/>
      <circle cx='265' cy='195' r='2' fill='{safe_theme}' fill-opacity='0.6'/>
      
      <rect x='45' y='360' width='85' height='70' rx='5' fill='#05060a' fill-opacity='0.8' stroke='{safe_theme}' stroke-width='1.5' stroke-opacity='0.45'/>
      <rect x='53' y='368' width='69' height='54' rx='3' fill='none' stroke='{safe_cyan}' stroke-width='1' stroke-opacity='0.3'/>

      <!-- Microchip Pins -->
      <path d='M250 195 H240 M250 205 H240 M250 215 H240 M250 225 H240 M250 235 H240 M250 245 H240' stroke='{safe_cyan}' stroke-width='1.2' stroke-opacity='0.6'/>
      <path d='M350 195 H360 M350 205 H360 M350 215 H360 M350 225 H360 M350 235 H360 M350 245 H360' stroke='{safe_theme}' stroke-width='1.2' stroke-opacity='0.5'/>
      <path d='M280 260 V270 M290 260 V270 M300 260 V270 M310 260 V270' stroke='{safe_cyan}' stroke-width='1.2' stroke-opacity='0.6'/>

      <!-- Data Bus Lines (Left Bus) -->
      <path d='M30 0 V110 L55 135 V280 L30 305 V600' stroke='{safe_cyan}' stroke-width='1.6' stroke-opacity='0.6' stroke-linecap='round' stroke-linejoin='round'/>
      <path d='M42 0 V90 L67 115 V260 L42 285 V600' stroke='{safe_theme}' stroke-width='1.3' stroke-opacity='0.45' stroke-linecap='round' stroke-linejoin='round'/>
      <circle cx='55' cy='135' r='3' fill='{safe_cyan}' fill-opacity='0.8'/>
      <circle cx='67' cy='115' r='2.5' fill='{safe_theme}' fill-opacity='0.7'/>

      <!-- Center-Right Circuit Bus -->
      <path d='M140 0 V130 L180 170 H220 L240 190 V320 L205 355 V600' stroke='{safe_cyan}' stroke-width='1.8' stroke-opacity='0.65' stroke-linecap='round' stroke-linejoin='round'/>
      <path d='M155 0 V115 L195 155 H235 L255 175' stroke='{safe_theme}' stroke-width='1.4' stroke-opacity='0.5' stroke-linecap='round' stroke-linejoin='round'/>
      <circle cx='180' cy='170' r='3' fill='{safe_cyan}' fill-opacity='0.85'/>
      <circle cx='205' cy='355' r='3' fill='{safe_cyan}' fill-opacity='0.85'/>

      <!-- Solder Ring Nodes -->
      <circle cx='205' cy='240' r='3.5' stroke='{safe_cyan}' stroke-width='1.2' fill='none' stroke-opacity='0.7'/>
      <circle cx='205' cy='240' r='1.5' fill='{safe_cyan}' fill-opacity='0.9'/>
      <circle cx='205' cy='260' r='3.5' stroke='{safe_theme}' stroke-width='1.2' fill='none' stroke-opacity='0.6'/>
      <circle cx='205' cy='260' r='1.5' fill='{safe_theme}' fill-opacity='0.8'/>
      <path d='M205 244 V256' stroke='{safe_theme}' stroke-width='1' stroke-opacity='0.5'/>

      <!-- Right Edge Traces -->
      <path d='M370 0 V120 L345 145 V290 L370 315 V600' stroke='{safe_theme}' stroke-width='1.6' stroke-opacity='0.5' stroke-linecap='round' stroke-linejoin='round'/>
      <path d='M382 0 V105 L357 130 V275 L382 300 V600' stroke='{safe_cyan}' stroke-width='1.3' stroke-opacity='0.55' stroke-linecap='round' stroke-linejoin='round'/>
      <circle cx='345' cy='145' r='2.8' fill='{safe_theme}' fill-opacity='0.75'/>
    </svg>"""
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def _compress_image_to_data_uri(file_bytes: bytes, mime_type: str, max_width: int, max_height: int, quality: int = 85) -> str:
    """Resize image to fit within max bounds and return optimized base64 data URI to stay well under Firestore limits."""
    if "gif" in mime_type.lower() and len(file_bytes) <= 800000:
        b64 = base64.b64encode(file_bytes).decode("ascii")
        return f"data:image/gif;base64,{b64}"
    import io
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img.save(buf, format="WEBP", quality=quality)
            out_mime = "image/webp"
        else:
            img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=quality)
            out_mime = "image/jpeg"
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:{out_mime};base64,{b64}"
    except Exception:
        b64 = base64.b64encode(file_bytes).decode("ascii")
        return f"data:{mime_type};base64,{b64}"


def build_discord_profile_card_html(username: str, profile_data: dict | None = None, is_preview: bool = False, preview_dict: dict | None = None) -> str:

    """Render the Discord-style cyberpunk animated profile card as HTML string."""
    if not username:
        return ""
    if is_preview and isinstance(preview_dict, dict):
        card_bg = preview_dict.get("cardBackground", "#111214")
        card_accent = preview_dict.get("themeColor", card_bg)
        b_type = preview_dict.get("bannerType", "color")
        b_val = preview_dict.get("bannerValue", "#5865F2")
        av_src = preview_dict.get("avatar")
        disp_text = html.escape(preview_dict.get("display_name") or username)
        bio_text = html.escape(preview_dict.get("summary") or "Surveillance operative on QUEST network")
        is_premium = bool(preview_dict.get("isPremium", False))
        active_anim = preview_dict.get("animationEffect", "none") if is_premium else "none"
        anim_int = preview_dict.get("animationIntensity", 2)
    else:
        if profile_data is None:
            try:
                profile_data = firebase_db.get_user_profile(username)
            except Exception:
                profile_data = {}

        stored = firebase_db.get_banner_customization(username)
        if isinstance(profile_data.get("banner_customization"), dict):
            stored.update(profile_data["banner_customization"])

        is_premium = bool(
            profile_data.get("is_pro")
            or profile_data.get("is_premium")
            or profile_data.get("profile_customization", {}).get("is_pro")
            or stored.get("isPremium")
            or firebase_db.is_user_pro(username)
        )
        card_bg = stored.get("cardBackground") or "#111214"
        card_accent = stored.get("themeColor") or stored.get("cardBackground") or profile_data.get("profile_customization", {}).get("accent_color") or "#8b5cf6"
        b_type = stored.get("bannerType", "color")
        b_val = stored.get("bannerValue") or card_accent
        av_src = profile_data.get("avatar")
        disp_text = html.escape(profile_data.get("display_name") or username)
        bio_text = html.escape(profile_data.get("summary") or "Surveillance operative on QUEST network")
        active_anim = stored.get("animationEffect", "neon_border" if is_premium else "none") if is_premium else "none"
        anim_int = stored.get("animationIntensity", 2)

    if not (isinstance(card_accent, str) and card_accent.startswith("#")):
        card_accent = "#8b5cf6"
    if not (isinstance(card_bg, str) and card_bg.startswith("#")):
        card_bg = "#111214"

    circuit_svg = _build_cyber_circuit_svg(theme_color=card_accent, cyan_accent="#38bdf8")

    if b_type == "image" and (b_val.startswith("data:") or b_val.startswith("http")):
        banner_inner = f'<div style="height:130px;background-image:url(\'{b_val}\');background-size:cover;background-position:center;border-bottom:1px solid {card_accent}55;"></div>'
    else:
        banner_inner = f'<div style="height:120px;position:relative;background:linear-gradient(180deg, {card_accent}33 0%, rgba(0,0,0,0.45) 100%);border-bottom:1px solid {card_accent}55;"></div>'

    if av_src:
        av_markup = f'<img src="{av_src}" alt="Avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block;">'
    else:
        initial = disp_text[:1].upper() if disp_text else "U"
        av_markup = f'<div style="width:100%;height:100%;display:grid;place-items:center;background:#1e2028;color:#fff;font-size:2rem;font-weight:700;">{initial}</div>'

    try:
        is_online = firebase_db.is_user_online(username)
    except Exception:
        is_online = False
    dot_color = "#23a55a" if is_online else "#6b7280"
    dot_glow = f"box-shadow:0 0 8px {dot_color}88;" if is_online else ""

    if anim_int == 1:
        glow_val = "22px"
        spread_val = "45px"
    elif anim_int == 3:
        glow_val = "55px"
        spread_val = "90px"
    else:
        glow_val = "35px"
        spread_val = "65px"

    anim_css = ""
    card_animation_style = ""
    extra_card_elements = ""

    if active_anim == "neon_border":
        anim_css = f"""
        @keyframes cyberNeonPulse {{
            0% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.65), 0 0 15px {card_accent}55, inset 0 0 15px {card_accent}25;
                border-color: {card_accent}77;
            }}
            50% {{
                box-shadow: 0 18px 55px rgba(0,0,0,0.85), 0 0 {glow_val} {card_accent}, 0 0 {spread_val} {card_accent}55, inset 0 0 30px {card_accent}44;
                border-color: {card_accent}ff;
            }}
            100% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.65), 0 0 15px {card_accent}55, inset 0 0 15px {card_accent}25;
                border-color: {card_accent}77;
            }}
        }}
        """
        card_animation_style = "animation: cyberNeonPulse 2.4s ease-in-out infinite;"

    elif active_anim == "holo_scanline":
        anim_css = f"""
        @keyframes holoScanlineMove {{
            0% {{ top: -4px; opacity: 0; }}
            12% {{ opacity: 0.95; }}
            88% {{ opacity: 0.95; }}
            100% {{ top: 100%; opacity: 0; }}
        }}
        @keyframes holoCardGlow {{
            0%, 100% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.65), 0 0 25px {card_accent}44, inset 0 0 20px {card_accent}20;
                border-color: {card_accent}88;
            }}
            50% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.75), 0 0 {glow_val} #38bdf8aa, inset 0 0 30px #38bdf833;
                border-color: #38bdf8;
            }}
        }}
        """
        card_animation_style = "animation: holoCardGlow 2.6s ease-in-out infinite;"
        extra_card_elements = f"""
        <div style="
            position: absolute;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, transparent 0%, {card_accent} 20%, #ffffff 50%, #38bdf8 80%, transparent 100%);
            box-shadow: 0 0 16px {card_accent}, 0 0 28px #38bdf8, 0 0 8px #fff;
            pointer-events: none;
            z-index: 25;
            animation: holoScanlineMove 2.6s linear infinite;
        "></div>
        """

    elif active_anim == "circuit_surge":
        anim_css = f"""
        @keyframes circuitPowerSurge {{
            0%, 100% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.65), 0 0 20px {card_accent}33, inset 0 0 20px {card_accent}15;
                filter: brightness(1);
                border-color: {card_accent}66;
            }}
            42% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.7), 0 0 25px {card_accent}55, inset 0 0 25px {card_accent}25;
                filter: brightness(1.05);
            }}
            50% {{
                box-shadow: 0 18px 55px rgba(0,0,0,0.85), 0 0 {spread_val} {card_accent}, 0 0 80px #38bdf899, inset 0 0 45px {card_accent}66;
                filter: brightness(1.35) contrast(1.15);
                border-color: #38bdf8;
            }}
            58% {{
                box-shadow: 0 18px 50px rgba(0,0,0,0.8), 0 0 35px {card_accent}aa, inset 0 0 30px {card_accent}44;
                filter: brightness(1.15);
                border-color: {card_accent}ff;
            }}
        }}
        """
        card_animation_style = "animation: circuitPowerSurge 2.8s ease-in-out infinite;"

    elif active_anim == "rgb_orbit":
        anim_css = f"""
        @keyframes rgbChromaOrbit {{
            0% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.7), 0 0 {glow_val} rgba(255, 0, 85, 0.6), inset 0 0 20px rgba(255, 0, 85, 0.2);
                border-color: #ff0055;
            }}
            25% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.7), 0 0 {glow_val} rgba(0, 240, 255, 0.6), inset 0 0 20px rgba(0, 240, 255, 0.2);
                border-color: #00f0ff;
            }}
            50% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.7), 0 0 {glow_val} rgba(168, 85, 247, 0.6), inset 0 0 20px rgba(168, 85, 247, 0.2);
                border-color: #a855f7;
            }}
            75% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.7), 0 0 {glow_val} rgba(234, 179, 8, 0.6), inset 0 0 20px rgba(234, 179, 8, 0.2);
                border-color: #eab308;
            }}
            100% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.7), 0 0 {glow_val} rgba(255, 0, 85, 0.6), inset 0 0 20px rgba(255, 0, 85, 0.2);
                border-color: #ff0055;
            }}
        }}
        """
        card_animation_style = "animation: rgbChromaOrbit 4.5s linear infinite;"

    elif active_anim == "glitch_aura":
        anim_css = f"""
        @keyframes glitchAuraEffect {{
            0% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.65), -3px -2px {glow_val} rgba(0,240,255,0.7), 3px 2px {glow_val} rgba(255,0,85,0.7), inset 0 0 15px {card_accent}33;
                border-color: {card_accent}88;
            }}
            33% {{
                box-shadow: 0 16px 50px rgba(0,0,0,0.75), 4px -3px {spread_val} rgba(0,240,255,0.85), -4px 3px {spread_val} rgba(255,0,85,0.85), inset 0 0 25px {card_accent}55;
                border-color: #00f0ff;
            }}
            66% {{
                box-shadow: 0 16px 50px rgba(0,0,0,0.75), -2px 4px {spread_val} rgba(0,240,255,0.8), 2px -4px {spread_val} rgba(255,0,85,0.8), inset 0 0 25px {card_accent}55;
                border-color: #ff0055;
            }}
            100% {{
                box-shadow: 0 16px 45px rgba(0,0,0,0.65), -3px -2px {glow_val} rgba(0,240,255,0.7), 3px 2px {glow_val} rgba(255,0,85,0.7), inset 0 0 15px {card_accent}33;
                border-color: {card_accent}88;
            }}
        }}
        """
        card_animation_style = "animation: glitchAuraEffect 2.2s ease-in-out infinite;"

    tier_badge_markup = f"""
    <div style="position:absolute;top:14px;right:14px;z-index:20;display:inline-flex;align-items:center;gap:5px;padding:5px 14px;border-radius:20px;border:1.5px solid {card_accent};background:rgba(8,10,18,0.75);backdrop-filter:blur(10px);box-shadow:0 0 16px {card_accent}55;">
        <span style="font-size:0.75rem;">👑</span>
        <span style="font-size:0.68rem;font-weight:800;letter-spacing:1px;color:#D4A843;text-transform:uppercase;font-family:'Inter',sans-serif;">PREMIUM PRO</span>
    </div>
    """ if is_premium else ""

    tier_crown_markup = '<span style="margin-left:auto;font-size:1.05rem;" title="Premium Pro Member">👑</span>' if is_premium else ''

    return f"""
<style>
{anim_css}
</style>
<div style="position:sticky;top:1rem;width:100%;max-width:440px;margin:0 auto;box-sizing:border-box;">
    <!-- Cyberpunk Circuit Profile Card -->
    <div style="
        position: relative;
        width: 100%;
        height: auto;
        min-height: 460px;
        background-color: {card_bg};
        background-image: 
            linear-gradient(180deg, rgba(8,10,16,0.72) 0%, rgba(5,6,12,0.92) 100%),
            url('{circuit_svg}');
        background-size: cover, 100% 600px;
        background-repeat: no-repeat, repeat-y;
        border-radius: 20px;
        border: 1.5px solid {card_accent}66;
        box-shadow: 0 16px 45px rgba(0,0,0,0.65), 0 0 25px {card_accent}33, inset 0 0 25px {card_accent}15;
        overflow: hidden;
        color: #fff;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        transition: border 0.3s ease, box-shadow 0.3s ease;
        box-sizing: border-box;
        {card_animation_style}
    ">
        {extra_card_elements}
        <!-- Top Right: Tier Pill Badge -->
        {tier_badge_markup}

        <!-- Top Banner Area -->
        {banner_inner}

        <!-- Overlapping Avatar (Discord Popout) -->
        <div style="padding:0 22px;margin-top:-44px;position:relative;z-index:5;box-sizing:border-box;">
            <div style="position:relative;width:84px;height:84px;">
                <div style="width:84px;height:84px;border-radius:50%;border:4px solid #080a10;box-shadow:0 0 16px {card_accent}55, 0 6px 16px rgba(0,0,0,0.5);overflow:hidden;background:#151720;box-sizing:border-box;">
                    {av_markup}
                </div>
                <!-- Discord Online Dot -->
                <div style="width:22px;height:22px;border-radius:50%;background:{dot_color};border:3.5px solid #080a10;position:absolute;bottom:2px;right:2px;box-sizing:border-box;{dot_glow}"></div>
            </div>

            <!-- Identity Header -->
            <div style="margin-top:12px;box-sizing:border-box;">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
                    <span style="font-size:1.25rem;font-weight:700;color:#f3f4f6;letter-spacing:-0.2px;word-break:break-word;overflow-wrap:anywhere;">{disp_text}</span>
                    {tier_crown_markup}
                </div>
                <div style="font-size:0.85rem;color:#9ca3af;margin-top:2px;word-break:break-word;overflow-wrap:anywhere;">@{username}</div>

                <!-- Profile Summary / About Me Container -->
                <div style="
                    margin-top:14px;
                    margin-bottom:20px;
                    background:rgba(6,8,14,0.72);
                    border-radius:10px;
                    border:1px solid {card_accent}33;
                    box-shadow:inset 0 0 15px rgba(0,0,0,0.4);
                    padding:14px 16px;
                    border-left:3px solid {card_accent};
                    box-sizing:border-box;
                    width:100%;
                    max-width:100%;
                    overflow:hidden;
                ">
                    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;color:{card_accent};letter-spacing:1px;margin-bottom:6px;">About Me</div>
                    <div style="
                        font-size:0.84rem;
                        color:#e5e7eb;
                        line-height:1.5;
                        word-break:break-word;
                        overflow-wrap:anywhere;
                        white-space:pre-wrap;
                        max-width:100%;
                        box-sizing:border-box;
                    ">{bio_text}</div>
                    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;color:#9ca3af;letter-spacing:1px;margin:12px 0 4px;">Member Since</div>
                    <div style="font-size:0.8rem;color:#cbd5e1;word-break:break-word;overflow-wrap:anywhere;">QUEST Surveillance Network</div>
                </div>
            </div>
        </div>
    </div>
</div>
"""



def _card_start(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="q-settings-heading" style="margin-bottom:18px;">'
        f'<h2 style="font-size:1.5rem;font-weight:700;color:var(--q-text);margin:0 0 4px;">{title}</h2>'
        f'<p style="font-size:0.88rem;color:var(--q-text-3);margin:0;">{subtitle}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render(user_info: dict, selected: str | None = None) -> None:
    if st.session_state.get("show_signout_dialog"):
        _signout_dialog()

    username = user_info.get("username", "")

    # Handle incoming OAuth callback if present in query params
    try:
        cb_result = oauth_connections.handle_callback(username)
        if cb_result and isinstance(cb_result, dict):
            p_name = cb_result.get("provider", "Account").title()
            st.success(f"Successfully connected {p_name}!")
            st.rerun()
    except Exception as exc:
        st.error(f"OAuth callback error: {exc}")

    # Fast session caching for profile data to avoid remote network latency on every interaction
    if "_cached_profile" not in st.session_state or st.session_state.get("_cached_profile_user") != username:
        try:
            profile = firebase_db.get_user_profile(username)
        except Exception:
            profile = dict(user_info)
        st.session_state._cached_profile = profile
        st.session_state._cached_profile_user = username
    else:
        profile = st.session_state._cached_profile

    st.markdown(
        '<div class="q-settings-title" style="margin-bottom:20px;">'
        '<span style="font-size:1.6rem;font-weight:700;letter-spacing:-0.5px;">Settings</span>'
        '</div>',
        unsafe_allow_html=True,
    )

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

    _render_section(selected, username, user_info, profile)


def _render_section(selected: str, username: str, user_info: dict, profile: dict) -> None:

    if selected == "Profile":
        _card_start("Profile", "Your public identity inside QUEST.")

        # ── 1. Determine Pro / Premium Tier ──
        is_user_pro = bool(
            firebase_db.is_user_pro(username)
            or profile.get("is_pro")
            or profile.get("is_premium")
            or profile.get("profile_customization", {}).get("is_pro")
            or profile.get("banner_customization", {}).get("isPremium")
            or user_info.get("is_pro")
            or user_info.get("profile_customization", {}).get("is_pro")
        )

        # ── 2. Read Stored Banner Customization Schema ──
        stored = profile.get("banner_customization")
        if not isinstance(stored, dict):
            stored = {}
        saved_custom = {
            "bannerType": stored.get("bannerType", "color"),
            "bannerValue": stored.get("bannerValue", "#5865F2"),
            "themeColor": stored.get("themeColor", "#5865F2"),
            "cardBackground": stored.get("cardBackground", "#111214"),
            "isPremium": is_user_pro or stored.get("isPremium", False),
            "animationEffect": stored.get("animationEffect", "neon_border"),
            "animationIntensity": stored.get("animationIntensity", 2),
        }

        # ── 3. Initialize In-Session Reactive Preview State ──
        if "_banner_preview" not in st.session_state or st.session_state.get("_banner_preview_user") != username:
            st.session_state._banner_preview = {
                "bannerType": saved_custom.get("bannerType", "color"),
                "bannerValue": saved_custom.get("bannerValue", "#5865F2"),
                "themeColor": saved_custom.get("themeColor", "#5865F2"),
                "cardBackground": saved_custom.get("cardBackground", "#111214"),
                "isPremium": saved_custom.get("isPremium", False),
                "animationEffect": saved_custom.get("animationEffect", "neon_border"),
                "animationIntensity": saved_custom.get("animationIntensity", 2),
                "display_name": profile.get("display_name", user_info.get("display_name", username)),
                "summary": profile.get("summary", ""),
                "avatar": profile.get("avatar") or user_info.get("avatar"),
            }
            st.session_state._banner_preview_user = username

        prev = st.session_state._banner_preview
        if is_user_pro and not prev.get("_manual_tier_toggle"):
            prev["isPremium"] = True

        # Upgrade notice dialog
        @st.dialog("⚡ Upgrade to QUEST Pro")
        def _show_upgrade_dialog():
            st.markdown("""
            <div style="text-align:center;padding:10px 0 16px;">
                <div style="font-size:2rem;margin-bottom:6px;">👑</div>
                <h3 style="margin:0 0 8px;color:#D4A843;font-weight:700;">Unlock Custom Profile Banners & Themes</h3>
                <p style="font-size:0.88rem;color:var(--q-text-2);line-height:1.5;">
                    Upgrade to <strong>QUEST Pro</strong> to upload custom image/GIF banners, personalize your profile card background, enable futuristic neon glowing borders, and display the exclusive PRO badge.
                </p>
                <div style="background:var(--q-surface-2);border-radius:12px;padding:14px;margin:16px 0;text-align:left;">
                    <div style="font-size:0.85rem;color:var(--q-text);font-weight:600;margin-bottom:6px;">Pro Membership Features:</div>
                    <div style="font-size:0.8rem;color:var(--q-text-3);line-height:1.6;">
                        ✓ Upload custom PNG, JPG, or animated GIF/WEBP banners (up to 10MB)<br>
                        ✓ Custom profile card backgrounds & theme gradients (like Discord Nitro)<br>
                        ✓ Animated neon borders, holographic scanlines, and circuit surges<br>
                        ✓ ⚡ PRO badge displayed on profile, chat & sidebar
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("👑 Activate Free Pro Pass in Preview", type="primary", use_container_width=True):
                prev["isPremium"] = True
                prev["_manual_tier_toggle"] = True
                st.toast("Pro features unlocked in live preview!", icon="🎉")
                st.rerun()

        # Two-column layout: Left = Controls, Right = Discord-Style Live Preview
        col_form, col_preview = st.columns([1.1, 0.9], gap="large")

        with col_form:
            # ── 1. MEMBERSHIP TIER SELECTOR (Basic vs Premium) ──
            is_premium = bool(prev.get("isPremium", False))
            st.markdown(
                '<div style="font-size:0.95rem;font-weight:700;color:var(--q-text);margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;">'
                '<span>Membership Tier</span>'
                f'<span style="font-size:0.75rem;font-weight:700;color:{"#D4A843" if is_premium else "#9ca3af"};background:{"rgba(212,168,67,0.15)" if is_premium else "rgba(255,255,255,0.06)"};padding:3px 10px;border-radius:12px;border:1px solid {"#D4A84355" if is_premium else "rgba(255,255,255,0.1)"};">{"👑 PREMIUM PRO" if is_premium else "BASIC"}</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.caption("Switch between Basic and Premium to preview and customize tier-specific features.")

            tier_options = ["Basic Member", "👑 Premium Member (Pro)"]
            current_tier_idx = 1 if is_premium else 0
            chosen_tier_str = st.radio(
                "Membership Tier",
                options=tier_options,
                index=current_tier_idx,
                horizontal=True,
                key="tier_selector_radio_choice",
                label_visibility="collapsed",
            )
            new_is_premium = (chosen_tier_str == "👑 Premium Member (Pro)")
            if new_is_premium != is_premium:
                prev["isPremium"] = new_is_premium
                prev["_manual_tier_toggle"] = True
                is_premium = new_is_premium
                st.rerun()

            st.markdown("<hr style='border:none;border-top:1px solid var(--q-border);margin:16px 0;'>", unsafe_allow_html=True)

            # ── 2. PROFILE CARD ANIMATIONS (PREMIUM EXCLUSIVE) ──
            st.markdown(
                '<div style="font-size:0.95rem;font-weight:700;color:var(--q-text);margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;">'
                '<span>Profile Card Animations</span>'
                f'<span style="font-size:0.72rem;font-weight:700;color:{"#D4A843" if is_premium else "var(--q-text-3)"};background:{"rgba(212,168,67,0.15)" if is_premium else "var(--q-surface-2)"};padding:2px 8px;border-radius:6px;">{"👑 UNLOCKED" if is_premium else "🔒 PREMIUM ONLY"}</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.caption("Customize your profile card with animated neon borders, holographic scanlines, and circuit surges.")

            if not is_premium:
                st.markdown(
                    '<div style="background:rgba(212,168,67,0.05);border:1px dashed rgba(212,168,67,0.3);border-radius:10px;padding:12px 14px;margin-bottom:12px;">'
                    '<div style="font-size:0.83rem;color:#D4A843;font-weight:600;margin-bottom:4px;">🔒 Exclusive to Premium Members</div>'
                    '<div style="font-size:0.78rem;color:var(--q-text-3);line-height:1.4;">'
                    'Animated neon pulsing borders, holographic laser scanlines, circuit power surges, and rainbow chroma streams are available exclusively for Premium members.<br>'
                    'Select <strong>👑 Premium Member (Pro)</strong> above to unlock and customize animations!'
                    '</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                anim_keys = [k for k, _, _ in _ANIMATION_OPTIONS]
                current_anim = prev.get("animationEffect", "neon_border")
                if current_anim not in anim_keys:
                    current_anim = "neon_border"

                anim_display_list = [f"{name} — {desc}" for _, name, desc in _ANIMATION_OPTIONS]
                current_anim_idx = anim_keys.index(current_anim)

                selected_anim_display = st.selectbox(
                    "Select Animation Style",
                    options=anim_display_list,
                    index=current_anim_idx,
                    key="profile_anim_selectbox",
                    help="Choose the cyber animation effect to display on your profile card",
                )
                chosen_anim_key = anim_keys[anim_display_list.index(selected_anim_display)]
                if chosen_anim_key != prev.get("animationEffect"):
                    prev["animationEffect"] = chosen_anim_key
                    st.rerun()

                # Animation Glow Intensity
                intensity_options = ["Subtle (Level 1)", "Balanced (Level 2)", "Overdrive / High Voltage (Level 3)"]
                current_intensity = prev.get("animationIntensity", 2)
                if not isinstance(current_intensity, int) or current_intensity not in [1, 2, 3]:
                    current_intensity = 2
                selected_int_label = st.select_slider(
                    "Animation Glow Intensity",
                    options=intensity_options,
                    value=intensity_options[current_intensity - 1],
                    key="profile_anim_intensity_slider",
                    help="Adjust the glow reach and brightness of the animation",
                )
                new_int_val = intensity_options.index(selected_int_label) + 1
                if new_int_val != prev.get("animationIntensity"):
                    prev["animationIntensity"] = new_int_val
                    st.rerun()

            st.markdown("<hr style='border:none;border-top:1px solid var(--q-border);margin:16px 0;'>", unsafe_allow_html=True)

            # ── 3. PROFILE BACKGROUND & THEME COLOR (The single color wheel picker) ──
            st.markdown(
                '<div style="font-size:0.95rem;font-weight:700;color:var(--q-text);margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;">'
                '<span>Profile Background & Theme Color</span>'
                f'<span style="font-size:0.72rem;font-weight:700;color:{"#D4A843" if is_premium else "var(--q-text-3)"};background:{"rgba(212,168,67,0.15)" if is_premium else "var(--q-surface-2)"};padding:2px 8px;border-radius:6px;">{"👑 PRO" if is_premium else "FREE"}</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.caption("Change your profile card background color, glow, and cybernetic circuit lines with the color wheel.")

            init_bg = prev.get("cardBackground", "#111214")
            if not (isinstance(init_bg, str) and init_bg.startswith("#")):
                init_bg = "#111214"

            c_hex1, c_hex2 = st.columns([1, 4])
            with c_hex1:
                custom_hex = st.color_picker(
                    "Profile Background Color",
                    value=init_bg,
                    key="profile_bg_hex_picker",
                    label_visibility="collapsed",
                    help="Click to open color wheel, spectrum, and intensity slider",
                )
                if custom_hex != prev.get("cardBackground"):
                    prev["cardBackground"] = custom_hex
                    prev["themeColor"] = custom_hex
                    st.rerun()
            with c_hex2:
                st.markdown(
                    f'<div style="font-size:0.85rem;color:var(--q-text-2);padding-top:6px;">Theme Hex: <code style="background:var(--q-surface-2);padding:2px 6px;border-radius:4px;color:{custom_hex};font-weight:600;">{custom_hex}</code></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<hr style='border:none;border-top:1px solid var(--q-border);margin:16px 0;'>", unsafe_allow_html=True)

            # ── 4. PROFILE BANNER SECTION (Top Rectangle) ──
            st.markdown(
                '<div style="font-size:0.95rem;font-weight:700;color:var(--q-text);margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;">'
                '<span>Profile Banner (Top Rectangle)</span>'
                f'<span style="font-size:0.72rem;font-weight:700;color:{"#D4A843" if is_premium else "var(--q-text-3)"};">{"👑 PRO UNLOCKED" if is_premium else "🔒 PRO (Locked)"}</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.caption("Upload a custom banner image or animated GIF for the top rectangle (PNG, JPG, Animated WEBP, GIF - up to 10MB).")

            if not is_premium:
                st.markdown(
                    '<div style="background:var(--q-surface-2);border:1px dashed var(--q-border);border-radius:10px;padding:12px;text-align:center;margin-bottom:12px;">'
                    '<div style="font-size:0.8rem;color:var(--q-text-3);margin-bottom:8px;">Custom image and animated GIF banners for the top rectangle are exclusive to QUEST Pro. Switch to <strong>👑 Premium Member (Pro)</strong> to enable image banners.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                banner_file = st.file_uploader(
                    "Upload Banner Image",
                    type=["png", "jpg", "jpeg", "webp", "gif"],
                    key="banner_file_uploader",
                    label_visibility="collapsed",
                    help="Upload a custom banner image or animated GIF/WEBP for the top rectangle (up to 10MB)",
                )
                if banner_file is not None:
                    file_sig = f"{banner_file.name}_{banner_file.size}"
                    if st.session_state.get("_last_banner_upload_sig") != file_sig:
                        if banner_file.size > 10485760:
                            st.error("Banner file must be under 10MB.")
                        else:
                            banner_uri = _compress_image_to_data_uri(
                                banner_file.getvalue(),
                                banner_file.type or "image/png",
                                max_width=960,
                                max_height=320,
                            )
                            prev["bannerType"] = "image"
                            prev["bannerValue"] = banner_uri
                            st.session_state._last_banner_upload_sig = file_sig
                            st.toast("Banner loaded in preview!")

                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if prev.get("bannerType") == "image":
                        st.markdown('<div style="font-size:0.8rem;color:#34d399;font-weight:600;padding-top:8px;">✓ Custom banner image loaded</div>', unsafe_allow_html=True)
                with b_col2:
                    if prev.get("bannerType") == "image" and st.button("🔄 Remove Banner Image", key="btn_reset_banner_img", use_container_width=True):
                        prev["bannerType"] = "color"
                        prev["bannerValue"] = "#5865F2"
                        st.session_state._last_banner_upload_sig = None
                        st.rerun()

            st.markdown("<hr style='border:none;border-top:1px solid var(--q-border);margin:16px 0;'>", unsafe_allow_html=True)

            # ── 5. AVATAR SECTION (PFP Circle - Available to ALL Users: Basic & Pro) ──
            st.markdown(
                '<div style="font-size:0.95rem;font-weight:700;color:var(--q-text);margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;">'
                '<span>Profile Picture (Avatar PFP)</span>'
                '<span style="font-size:0.72rem;color:var(--q-text-3);">Free & Pro</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.caption("Upload your custom profile picture for the round avatar (PFP). Available to everyone.")
            avatar_upload = st.file_uploader(
                "Avatar Upload",
                type=["png", "jpg", "jpeg", "webp"],
                key="avatar_upload_input",
                label_visibility="collapsed",
                help="PNG, JPG, WEBP • Saves to circular PFP",
            )
            if avatar_upload is not None:
                av_sig = f"{avatar_upload.name}_{avatar_upload.size}"
                if st.session_state.get("_last_avatar_upload_sig") != av_sig:
                    if avatar_upload.size > 10485760:
                        st.error("Avatar file must be under 10MB.")
                    else:
                        av_uri = _compress_image_to_data_uri(
                            avatar_upload.getvalue(),
                            avatar_upload.type or "image/png",
                            max_width=256,
                            max_height=256,
                        )
                        prev["avatar"] = av_uri
                        st.session_state._last_avatar_upload_sig = av_sig
                        st.toast("Avatar loaded in preview!")

            av1, av2 = st.columns(2)
            with av1:
                if prev.get("avatar"):
                    st.markdown('<div style="font-size:0.8rem;color:#34d399;font-weight:600;padding-top:8px;">✓ Avatar selected</div>', unsafe_allow_html=True)
            with av2:
                if prev.get("avatar") and st.button("🗑️ Delete Avatar", key="btn_delete_avatar", use_container_width=True):
                    prev["avatar"] = None
                    st.session_state._last_avatar_upload_sig = None
                    st.rerun()

            st.markdown("<hr style='border:none;border-top:1px solid var(--q-border);margin:16px 0;'>", unsafe_allow_html=True)

            # ── 6. DISPLAY NAME & PROFILE SUMMARY ──
            new_disp = st.text_input(
                "Display name",
                value=prev.get("display_name", username),
                key="disp_name_input",
            )
            prev["display_name"] = new_disp

            new_summary = st.text_area(
                "Profile summary",
                value=prev.get("summary", ""),
                max_chars=240,
                placeholder="Short line about your investing style",
                key="summary_input",
            )
            prev["summary"] = new_summary

            st.markdown("<hr style='border:none;border-top:1px solid var(--q-border);margin:20px 0;'>", unsafe_allow_html=True)

            # ── 7. SAVE PROFILE BUTTON ──
            if st.button("Save profile", type="primary", use_container_width=True, key="btn_save_profile_main"):
                disp_val = prev.get("display_name", username).strip() or username
                summ_val = prev.get("summary", "")
                try:
                    firebase_db.update_profile(username, disp_val, summ_val)
                    st.session_state.user_info["display_name"] = disp_val
                    profile["display_name"] = disp_val
                    profile["summary"] = summ_val
                except Exception as e:
                    print(f"Error updating profile: {e}")

                try:
                    av_target = prev.get("avatar")
                    firebase_db.save_avatar(username, av_target)
                    if av_target:
                        st.session_state.user_info["avatar"] = av_target
                        profile["avatar"] = av_target
                    else:
                        st.session_state.user_info.pop("avatar", None)
                        profile["avatar"] = None
                except Exception as e:
                    print(f"Error saving avatar: {e}")

                banner_type_to_save = prev.get("bannerType", "color")
                if not is_premium and banner_type_to_save == "image":
                    banner_type_to_save = "color"
                    prev["bannerType"] = "color"

                schema_payload = {
                    "bannerType": banner_type_to_save,
                    "bannerValue": prev.get("bannerValue", "#5865F2"),
                    "themeColor": prev.get("themeColor", custom_hex),
                    "cardBackground": prev.get("cardBackground", custom_hex),
                    "isPremium": is_premium,
                    "animationEffect": prev.get("animationEffect", "none") if is_premium else "none",
                    "animationIntensity": prev.get("animationIntensity", 2) if is_premium else 1,
                }
                ok = firebase_db.save_banner_customization(username, schema_payload)
                try:
                    firebase_db.set_pro_status(username, is_premium)
                except Exception:
                    pass

                if ok:
                    profile["banner_customization"] = schema_payload
                    profile["is_pro"] = is_premium
                    profile["is_premium"] = is_premium
                    st.session_state.user_info["is_pro"] = is_premium
                    st.session_state.user_info["is_premium"] = is_premium
                    st.session_state.pop("_cached_profile", None)
                    st.session_state.pop("_user_profiles_cache", None)
                    st.toast("Profile settings saved successfully!", icon="✅")
                    st.rerun()
                else:
                    st.error("Could not save profile customizations.")

        # ── RIGHT COLUMN: CYBERPUNK LIVE PREVIEW CARD (With Live Animations) ──
        with col_preview:
            discord_card_html = build_discord_profile_card_html(
                username=username,
                profile_data=profile,
                is_preview=True,
                preview_dict=prev,
            )
            st.markdown(discord_card_html, unsafe_allow_html=True)


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

