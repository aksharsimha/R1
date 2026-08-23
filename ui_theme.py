"""
QUEST — UI Theme & Design System (Phase 0 foundation)
=====================================================
Single source of truth for the redesigned look & feel:

- Design tokens (colours, type, spacing, radius, motion) as CSS variables
- Two themes — 'light' (calm) and 'dark' (refined) — swappable at runtime
- Base Streamlit overrides that flatten the old "gaming" aesthetic
- Reusable component helpers that return HTML strings

Usage (in app.py):
    import ui_theme
    ui_theme.init_theme()          # once, near the top, after auth
    st.markdown(ui_theme.css(), unsafe_allow_html=True)
    ui_theme.theme_toggle()        # renders the sidebar switch
    st.markdown(ui_theme.metric_card("Invested", "₹40,576"), unsafe_allow_html=True)

Nothing here touches portfolio logic — it is pure presentation.
"""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:  # allows import in tests without Streamlit runtime
    st = None


# =====================================================================
# Design tokens — two palettes sharing the same variable names
# =====================================================================
DARK = {
    "bg":          "#0F1115",
    "surface":     "#16181D",
    "surface_2":   "#1C1F25",
    "border":      "#262A31",
    "border_2":    "#2E333B",
    "text":        "#F1F3F5",
    "text_2":      "#B7BCC4",
    "text_3":      "#7E8590",
    "accent":      "#5DCAA5",   # brand teal
    "accent_weak": "#1D3A33",
    "pos":         "#5DCAA5",   # gains
    "neg":         "#F0997B",   # losses (calm coral, not alarm-red)
    "warn":        "#EF9F27",
    "warn_weak":   "#2A1F0E",
    "neg_weak":    "#2A1A1A",
    "pos_weak":    "#16271F",
}

LIGHT = {
    "bg":          "#F7F6F2",
    "surface":     "#FFFFFF",
    "surface_2":   "#F1EFE8",
    "border":      "#E4E2DA",
    "border_2":    "#D3D1C7",
    "text":        "#2C2C2A",
    "text_2":      "#5F5E5A",
    "text_3":      "#8A887F",
    "accent":      "#0F6E56",
    "accent_weak": "#E1F5EE",
    "pos":         "#0F6E56",
    "neg":         "#993C1D",
    "warn":        "#854F0B",
    "warn_weak":   "#FAEEDA",
    "neg_weak":    "#FAECE7",
    "pos_weak":    "#E1F5EE",
}

THEMES = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME = "dark"


# =====================================================================
# Theme state
# =====================================================================
def init_theme():
    """Ensure a theme is set in session_state."""
    if st is not None and "ui_theme" not in st.session_state:
        st.session_state.ui_theme = DEFAULT_THEME


def current_theme() -> str:
    if st is None:
        return DEFAULT_THEME
    return st.session_state.get("ui_theme", DEFAULT_THEME)


def palette(theme: str = None) -> dict:
    return THEMES.get(theme or current_theme(), DARK)


def theme_toggle():
    """Render a compact light/dark switch in the sidebar."""
    if st is None:
        return
    init_theme()
    is_dark = current_theme() == "dark"
    label = "🌙  Dark" if is_dark else "☀️  Light"
    if st.sidebar.button(f"{label}  ·  switch theme", use_container_width=True,
                         key="ui_theme_toggle"):
        st.session_state.ui_theme = "light" if is_dark else "dark"
        st.rerun()


# =====================================================================
# CSS — tokens as variables + flat base overrides + motion
# =====================================================================
def css(theme: str = None) -> str:
    p = palette(theme)
    vars_block = "\n".join(f"        --q-{k.replace('_','-')}: {v};"
                           for k, v in p.items())
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {{
{vars_block}
        --q-radius: 12px;
        --q-radius-sm: 10px;
        --q-radius-lg: 16px;
        --q-gap: 12px;
        --q-ease: cubic-bezier(.22,.61,.36,1);
    }}

    /* ── Flatten the old gaming look ── */
    html, body {{ background: var(--q-bg) !important; }}
    .stApp {{ background: var(--q-bg) !important; color: var(--q-text);
              font-family: 'Inter', sans-serif; }}
    .stApp::before {{ display: none !important; }}   /* kill aurora */
    .block-container {{ max-width: 1200px; padding-top: 2.2rem;
        animation: q-page-in .38s var(--q-ease); }}
    @keyframes q-page-in {{ from {{ opacity: 0; transform: translateY(8px); }}
                            to {{ opacity: 1; transform: translateY(0); }} }}

    h1, h2, h3, h4 {{ color: var(--q-text); font-weight: 500;
                      letter-spacing: -0.2px; }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{ background: var(--q-surface) !important;
        border-right: 1px solid var(--q-border); }}
    /* Force every Streamlit wrapper inside the sidebar to fill the full width.
       This is the chain: stSidebarContent → stVerticalBlock → stMarkdownContainer
       → stRadio → radiogroup → label. Every node must be 100% wide with no
       internal padding that would create an asymmetric right gap. */
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-testid="stRadio"],
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
    section[data-testid="stSidebar"] [data-testid="stElementContainer"] {{
        width: 100% !important; max-width: 100% !important;
        box-sizing: border-box !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {{
        width: 100% !important; max-width: none !important; gap: 0 !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div {{
        padding-left: 0 !important; padding-right: 0 !important; min-width: 0 !important;
    }}
    button[data-testid="stSidebarCollapseButton"],
    button[kind="header"] {{
        visibility: hidden !important; width: 0 !important; min-width: 0 !important;
        height: 0 !important; padding: 0 !important; }}

    #quest-hamburger {{ position: fixed; top: 14px; left: 14px; z-index: 100000;
        width: 34px; height: 42px; display: flex; flex-direction: column;
        align-items: center; justify-content: center; gap: 4px; padding: 6px;
        border: 1px solid var(--q-border-2); border-radius: 9px;
        background: var(--q-surface); color: var(--q-accent); cursor: pointer; }}
    #quest-hamburger span {{ display: block; width: 3px; height: 19px;
        border-radius: 2px; background: currentColor; transition: height .15s var(--q-ease); }}
    #quest-hamburger:hover {{ background: var(--q-accent-weak); }}
    section[data-testid="stSidebar"] .stButton > button {{ min-height: 40px; }}

    /* ── Sidebar icon buttons (settings / bell) — real st.button() wrappers ── */
    /* The two icon buttons sit inside a horizontal block; strip all extra padding/margin
       so they share the same left/right edge as every other sidebar element. */
    .quest-icon-btn-row {{ width: 100%; display: flex; align-items: center;
        justify-content: space-between; gap: 8px; box-sizing: border-box; margin-bottom: 4px; }}
    .quest-icon-btn-row [data-testid="stElementContainer"],
    .quest-icon-btn-row [data-testid="stColumn"],
    .quest-icon-btn-row .stButton {{
        width: 100% !important; max-width: 100% !important; box-sizing: border-box !important;
        padding: 0 !important; margin: 0 !important; flex: 1 !important;
    }}
    /* Style the actual <button> element inside each icon wrapper */
    .quest-icon-btn-row .stButton > button {{
        width: 100% !important; height: 38px; min-height: 38px;
        padding: 0 !important; margin: 0 !important;
        background: var(--q-surface-2) !important;
        color: var(--q-text-2) !important;
        border: 1px solid var(--q-border-2) !important;
        border-radius: var(--q-radius-sm) !important;
        font-size: 1.05rem !important; display: flex; align-items: center;
        justify-content: center; box-sizing: border-box;
        transition: background .15s var(--q-ease), color .15s var(--q-ease); }}
    .quest-icon-btn-row .stButton > button:hover {{
        background: var(--q-accent-weak) !important; color: var(--q-accent) !important; }}
    /* Keep the old .quest-sidebar-icon class for any legacy HTML that still uses it */
    .quest-sidebar-icon-row {{ width: 100%; display: flex; align-items: center;
        justify-content: space-between; margin: 0; padding: 0; box-sizing: border-box; }}
    .quest-sidebar-icon {{ width: 38px; height: 38px; display: grid; place-items: center;
        color: var(--q-text-2); background: var(--q-surface-2); border: 1px solid var(--q-border-2);
        border-radius: var(--q-radius-sm); text-decoration: none; font-size: 1.05rem;
        box-sizing: border-box; transition: background .15s var(--q-ease), color .15s var(--q-ease); }}
    .quest-sidebar-icon:hover {{ background: var(--q-accent-weak); color: var(--q-accent); }}

    /* ── Nav radio: full-width card-style items ──
       The fix for the right-edge gap: both [role="radiogroup"] itself AND its
       parent stRadio wrapper must be explicitly 100% wide with box-sizing:border-box.
       Then each <label> child is also 100% wide — and all three together reach
       exactly the same right edge as the profile card and selectbox above them. */
    section[data-testid="stSidebar"] [role="radiogroup"] {{
        gap: 8px; width: 100% !important; box-sizing: border-box !important;
        display: flex; flex-direction: column; }}
    section[data-testid="stSidebar"] [role="radiogroup"] > label {{
        width: 100% !important; box-sizing: border-box !important;
        padding: 11px 12px; border: 1px solid var(--q-border);
        border-radius: var(--q-radius-sm); cursor: pointer;
        background: var(--q-surface-2);
        color: var(--q-text-2); transition: background .15s var(--q-ease),
        color .15s var(--q-ease), border-color .15s var(--q-ease); margin: 0; }}
    section[data-testid="stSidebar"] [role="radiogroup"] > label:hover {{
        background: var(--q-accent-weak); color: var(--q-text); border-color: var(--q-border-2); }}
    section[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child {{
        display: none !important; }}   /* hide the radio circle */
    section[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {{
        background: var(--q-accent-weak); color: var(--q-accent); border-color: var(--q-accent); font-weight: 500; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label p {{ font-size: .95rem; }}

    /* ── Buttons ── */
    .stButton > button {{ background: var(--q-surface-2); color: var(--q-text);
        border: 1px solid var(--q-border-2); border-radius: var(--q-radius-sm);
        font-weight: 500; transition: background .18s var(--q-ease),
        transform .12s var(--q-ease); }}
    .stButton > button:hover {{ background: var(--q-accent-weak);
        border-color: var(--q-accent); }}
    .stButton > button:active {{ transform: scale(.98); }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--q-border); }}
    .stTabs [data-baseweb="tab"] {{ color: var(--q-text-3); font-weight: 500;
        background: transparent; }}
    .stTabs [aria-selected="true"] {{ color: var(--q-text);
        border-bottom: 2px solid var(--q-accent); }}

    /* ── Dataframe ── */
    div[data-testid="stDataFrame"] {{ border: 1px solid var(--q-border);
        border-radius: var(--q-radius); overflow: hidden; }}

    /* ── Reusable component classes ── */
    .q-card {{ background: var(--q-surface); border: 1px solid var(--q-border);
        border-radius: var(--q-radius-lg); padding: 18px 20px;
        transition: transform .16s var(--q-ease), border-color .16s var(--q-ease); }}
    .q-card:hover {{ transform: translateY(-2px); border-color: var(--q-border-2); }}
    .q-metric {{ background: var(--q-surface-2); border-radius: var(--q-radius);
        padding: 12px 14px; }}
    .q-metric .lbl {{ font-size: .72rem; color: var(--q-text-3);
        text-transform: uppercase; letter-spacing: .6px; }}
    .q-metric .val {{ font-size: 1.15rem; color: var(--q-text); font-weight: 500;
        font-family: 'JetBrains Mono', monospace; margin-top: 2px; }}
    .q-row {{ display: flex; justify-content: space-between; align-items: center;
        background: var(--q-surface-2); border-radius: var(--q-radius-sm);
        padding: 11px 13px; transition: transform .14s var(--q-ease),
        background .3s var(--q-ease); }}
    .q-row:hover {{ transform: translateY(-1px); }}
    .q-mono {{ font-family: 'JetBrains Mono', monospace; }}
    .q-pos {{ color: var(--q-pos); }}
    .q-neg {{ color: var(--q-neg); }}
    .q-pill {{ display: inline-flex; align-items: center; gap: 5px;
        font-size: .72rem; padding: 3px 10px; border-radius: 999px; }}

    /* ── Legacy components (kept until their phase is restyled) ── */
    .dashboard-header {{ padding: 0 0 .5rem; margin-bottom: .5rem; }}
    .dashboard-header h1 {{ font-size: 2rem; font-weight: 500; margin: 0;
        color: var(--q-text); letter-spacing: -0.5px; }}
    .dashboard-header p {{ color: var(--q-text-3); margin: 2px 0 0;
        font-size: .9rem; }}
    .quest-profile-card {{ background: var(--q-surface-2);
        border: 1px solid var(--q-border); border-radius: var(--q-radius);
        padding: 28px 14px 14px; display: flex; align-items: center; gap: 10px;
        position: relative; }}
    .quest-profile-actions {{ position: absolute; top: 8px; left: 12px; right: 12px;
        display: flex; justify-content: space-between; color: var(--q-text-3); font-size: .9rem; }}
    .quest-profile-avatar {{ width: 38px; height: 38px; flex: 0 0 38px;
        display: grid; place-items: center; overflow: hidden; border-radius: 50%;
        background: var(--q-accent-weak); color: var(--q-accent); font-weight: 600; }}
    .quest-profile-avatar img {{ width: 100%; height: 100%; object-fit: cover; }}
    .quest-profile-copy {{ min-width: 0; }}
    .quest-profile-label {{ font-size: .68rem; color: var(--q-text-3);
        text-transform: uppercase; letter-spacing: .6px; }}
    .quest-profile-name {{ font-size: .95rem; color: var(--q-text);
        font-weight: 500; margin-top: 2px; }}
    .quest-profile-user {{ font-size: .78rem; color: var(--q-accent); }}
    .quest-nav-label {{ color: var(--q-text-3); font-size: .7rem; text-transform: uppercase;
        letter-spacing: .08em; margin: 16px 0 8px; }}
    .quest-settings-sidebar-title {{ color: var(--q-text); font-size: 1.2rem;
        font-weight: 500; padding: 8px 0 18px; border-bottom: 1px solid var(--q-border); }}
    .q-settings-title {{ border-bottom: 1px solid var(--q-border); padding-bottom: 14px;
        margin-bottom: 18px; }}
    .q-settings-title span {{ display: block; color: var(--q-text); font-size: 1.8rem; font-weight: 500; }}
    .q-settings-title small, .q-settings-heading p {{ color: var(--q-text-3); }}
    .q-settings-heading {{ background: var(--q-surface); border: 1px solid var(--q-border);
        border-radius: var(--q-radius-lg); padding: 18px 20px 4px; margin-bottom: 0; }}
    .q-settings-heading h2 {{ margin: 0; font-size: 1.15rem; }}
    .q-settings-heading p {{ font-size: .82rem; margin-top: 5px; }}
    .q-avatar-large {{ width: 76px; height: 76px; object-fit: cover; border-radius: 50%;
        border: 2px solid var(--q-accent); margin: 4px 0 12px; }}
    .q-avatar-placeholder {{ display: grid; place-items: center; background: var(--q-accent-weak);
        color: var(--q-accent); font-size: 1.8rem; font-weight: 600; }}
    .q-settings-rail-title {{ color: var(--q-text-3); font-size: .68rem; letter-spacing: .12em;
        margin: 5px 0 10px; }}
    [data-testid="stVerticalBlock"]:has(.q-settings-rail-marker) [role="radiogroup"] {{ gap: 6px; }}
    [data-testid="stVerticalBlock"]:has(.q-settings-rail-marker) [role="radiogroup"] > label {{
        padding: 11px 12px; border-radius: var(--q-radius-sm); color: var(--q-text-2);
        cursor: pointer; transition: background .15s var(--q-ease), color .15s var(--q-ease); }}
    [data-testid="stVerticalBlock"]:has(.q-settings-rail-marker) [role="radiogroup"] > label:hover {{
        background: var(--q-surface-2); color: var(--q-text); }}
    [data-testid="stVerticalBlock"]:has(.q-settings-rail-marker) [role="radiogroup"] > label:has(input:checked) {{
        background: var(--q-surface-2); color: var(--q-text); font-weight: 500; }}
    [data-testid="stVerticalBlock"]:has(.q-settings-rail-marker) [role="radiogroup"] > label > div:first-child {{
        display: none !important; }}

    /* ── Motion ── */
    @keyframes q-fade {{ from {{ opacity: 0; transform: translateY(8px); }}
                         to {{ opacity: 1; transform: translateY(0); }} }}
    .q-enter {{ animation: q-fade .5s var(--q-ease) both; }}
    @keyframes q-shimmer {{ 0% {{ background-position: -400px 0; }}
                            100% {{ background-position: 400px 0; }} }}
    /* Allocation bars grow from 0 on load */
    @keyframes q-grow {{ from {{ width: 0 !important; }} }}
    .q-bar {{ animation: q-grow .9s var(--q-ease) both; }}
    /* Subtle pulse for the live-market pill */
    @keyframes q-pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .55; }} }}
    .q-live {{ animation: q-pulse 1.8s ease-in-out infinite; }}
    .q-skeleton {{ background: linear-gradient(90deg, var(--q-surface-2) 25%,
        var(--q-border) 37%, var(--q-surface-2) 63%);
        background-size: 800px 100%; animation: q-shimmer 1.4s infinite; }}

    /* ── Mobile Responsiveness ── */
    @media (max-width: 768px) {{
        .block-container {{ padding: 1rem 0.5rem !important; }}
        .dashboard-header h1 {{ font-size: 1.5rem !important; }}
        .dashboard-header p {{ font-size: 0.8rem !important; }}
        .q-card {{ padding: 12px 14px !important; }}
        .q-metric {{ padding: 10px 12px !important; }}
        .q-metric .val {{ font-size: 1rem !important; }}
        /* Let columns stack instead of squeezing */
        div[data-testid="column"] {{ min-width: 100% !important; }}
        /* Shrink the massive portfolio value font on phones */
        #qv {{ font-size: 1.8rem !important; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        .q-enter, .q-skeleton, .q-bar, .q-live, .block-container {{ animation: none !important; }}
        .q-row:hover, .q-card:hover {{ transform: none; }}
    }}
</style>
"""


# =====================================================================
# Component helpers (return HTML strings)
# =====================================================================
def metric_card(label: str, value: str, accent: str = None) -> str:
    color = f"color:var(--q-{accent});" if accent else ""
    return (f'<div class="q-metric"><div class="lbl">{label}</div>'
            f'<div class="val" style="{color}">{value}</div></div>')


def pill(text: str, tone: str = "accent", icon: str = "") -> str:
    """tone: accent | pos | neg | warn"""
    bg = {"accent": "var(--q-accent-weak)", "pos": "var(--q-pos-weak)",
          "neg": "var(--q-neg-weak)", "warn": "var(--q-warn-weak)"}.get(tone, "var(--q-accent-weak)")
    fg = f"var(--q-{ 'accent' if tone=='accent' else tone })"
    ic = f"{icon} " if icon else ""
    return f'<span class="q-pill" style="background:{bg};color:{fg};">{ic}{text}</span>'


def holding_row(name: str, sub: str, value: str, change: str,
                positive: bool = True) -> str:
    cls = "q-pos" if positive else "q-neg"
    return (
        f'<div class="q-row q-enter">'
        f'<div><div style="font-size:.82rem;font-weight:500;color:var(--q-text);">{name}</div>'
        f'<div style="font-size:.7rem;color:var(--q-text-3);">{sub}</div></div>'
        f'<div style="text-align:right;">'
        f'<div class="q-mono" style="font-size:.82rem;color:var(--q-text);">{value}</div>'
        f'<div class="q-mono {cls}" style="font-size:.7rem;">{change}</div></div>'
        f'</div>'
    )


def style_fig(fig):
    """Apply the active theme to any Plotly figure (in place). Returns fig."""
    p = palette()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=p["text_2"]),
        colorway=[p["accent"], p["warn"], p["neg"], "#85B7EB", p["text_3"], "#AFA9EC"],
        legend=dict(font=dict(color=p["text_2"])),
        hoverlabel=dict(bgcolor=p["surface"], font=dict(color=p["text"]),
                        bordercolor=p["border"]),
    )
    try:
        fig.update_xaxes(gridcolor=p["border"], zerolinecolor=p["border"],
                         linecolor=p["border"], color=p["text_3"])
        fig.update_yaxes(gridcolor=p["border"], zerolinecolor=p["border"],
                         linecolor=p["border"], color=p["text_3"])
    except Exception:
        pass  # figures without cartesian axes (pie, indicator)
    return fig


def value_hero(label: str, value: str, change: str, positive: bool = True) -> str:
    cls = "q-pos" if positive else "q-neg"
    return (
        f'<div style="margin-bottom:4px;">'
        f'<div style="font-size:.78rem;color:var(--q-text-3);">{label}</div>'
        f'<div class="q-mono" style="font-size:2.1rem;font-weight:500;color:var(--q-text);'
        f'letter-spacing:-1px;">{value}</div>'
        f'<div class="q-mono {cls}" style="font-size:.95rem;font-weight:500;">{change}</div>'
        f'</div>'
    )
