"""
QUEST Leaderboard Tab
====================
Interactive, high-fidelity competitive leaderboard displaying live registered users,
dynamic ranking criteria (Net Worth, Total XP, Returns, Losses), timeframes (1M, 3M, 6M, 1Y),
tier filters (Top 10, Top 50, Top 100, Top 200), Discord-style tiered podium, and a pinned
personal standing card for the active user.
"""

import streamlit as st
import streamlit.components.v1 as components
import json
import os
import firebase_db

def get_leaderboard_players():
    """
    Fetch all registered users from Firestore / local data and format them
    for the Leaderboard.
    """
    fallback_usernames = [
        ("28ryzo", "RS"),
        ("akshar", "AK"),
        ("akshar2", "A2"),
        ("akshar45", "A4"),
        ("amanraj", "AR"),
        ("krish_surne", "KS"),
        ("thaheer", "TH"),
        ("thaheer_basha", "TB"),
        ("vanshika", "VA"),
    ]
    
    users_dict = {}
    
    # 1. Try Firebase DB
    try:
        all_u = firebase_db.get_all_users()
        if all_u:
            for u in all_u:
                uname = u.get("username")
                if uname:
                    dname = u.get("display_name", uname)
                    initials = "".join([part[0].upper() for part in dname.split()[:2]]) if dname else uname[:2].upper()
                    if len(initials) < 2:
                        initials = uname[:2].upper()
                    users_dict[uname] = {
                        "username": uname,
                        "display_name": dname,
                        "avatar": initials,
                        "level": u.get("level", 1),
                        "netWorth": u.get("net_worth", 0),
                        "xp": u.get("xp", 0),
                        "change24h": u.get("change24h", 0.0),
                        "streak": u.get("streak", 0),
                    }
    except Exception:
        pass

    # 2. Check local users folder
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        users_dir = os.path.join(os.path.dirname(here), "users")
        if os.path.exists(users_dir):
            for folder in os.listdir(users_dir):
                if folder not in users_dict and not folder.startswith("."):
                    users_dict[folder] = {
                        "username": folder,
                        "display_name": folder,
                        "avatar": folder[:2].upper(),
                        "level": 1,
                        "netWorth": 0,
                        "xp": 0,
                        "change24h": 0.0,
                        "streak": 0,
                    }
    except Exception:
        pass

    # 3. Ensure fallback defaults are always present
    for uname, initials in fallback_usernames:
        if uname not in users_dict:
            users_dict[uname] = {
                "username": uname,
                "display_name": uname,
                "avatar": initials,
                "level": 1,
                "netWorth": 0,
                "xp": 0,
                "change24h": 0.0,
                "streak": 0,
            }

    players = []
    for idx, (uname, data) in enumerate(users_dict.items(), start=1):
        players.append({
            "id": idx,
            "username": data["username"],
            "avatar": data["avatar"],
            "level": data.get("level", 1),
            "netWorth": data.get("netWorth", 0),
            "xp": data.get("xp", 0),
            "change24h": data.get("change24h", 0.0),
            "streak": data.get("streak", 0),
            "returns": {"1M": 0, "3M": 0, "6M": 0, "1Y": 0},
            "losses": {"1M": 0, "3M": 0, "6M": 0, "1Y": 0},
        })

    return players

def build_leaderboard_html(players, active_username):
    players_json = json.dumps(players)
    active_user_json = json.dumps(active_username)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>QUEST Leaderboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:          #07080d;
      --surface:     #0c0e14;
      --surface-hi:  #10131e;
      --border:      rgba(124,47,255,0.2);
      --border-subtle: #1a1d28;
      --text:        #e8eaf0;
      --text-mid:    #d4d8e8;
      --text-dim:    #4b5163;
      --text-muted:  #2e3347;
      --label:       #4b5163;
      --cyan:        #00C9B1;
      --red:         #FF2F6B;
      --orange:      #FF8C42;
      --green:       #00C9B1;
      --loss-red:    #f87171;
      --streak:      #e8a02a;
      --grad:        linear-gradient(135deg, #7B2FFF 0%, #00C9B1 100%);
      --grad-subtle: linear-gradient(135deg, #7B2FFF22 0%, #00C9B122 100%);
      --grad-loss:   linear-gradient(135deg, #FF2F6B 0%, #FF8C42 100%);
      --grad-loss-s: linear-gradient(135deg, #FF2F6B22 0%, #FF8C4222 100%);
      --gold:        #f5c842;
      --silver:      #b0b8cc;
      --bronze:      #cd7c3a;
      --sans:        'Inter', system-ui, sans-serif;
      --mono:        'JetBrains Mono', monospace;
    }}

    html, body {{
      height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      overflow-x: hidden;
    }}

    body::-webkit-scrollbar {{ width: 5px; }}
    body::-webkit-scrollbar-track {{ background: transparent; }}
    body::-webkit-scrollbar-thumb {{ background: #1a1d28; border-radius: 3px; }}

    .wrap {{
      max-width: 1140px;
      margin: 0 auto;
      padding: 24px 28px 60px;
    }}

    /* ── Header ── */
    header {{
      padding: 20px 0 24px;
      border-bottom: 1px solid var(--border);
    }}
    .header-inner {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}

    .season-label {{
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      margin-bottom: 4px;
      background: var(--grad);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      transition: background 0.25s;
    }}
    .season-label.loss-mode {{
      background: var(--grad-loss);
      -webkit-background-clip: text;
      background-clip: text;
    }}

    h1 {{
      font-size: clamp(26px, 4vw, 34px);
      font-weight: 900;
      letter-spacing: -0.03em;
      color: #f0f2ff;
      line-height: 1.1;
      margin: 0;
    }}
    .subtitle {{
      font-size: 12px;
      color: var(--text-dim);
      margin-top: 6px;
      font-family: var(--mono);
    }}

    /* ── Controls ── */
    .controls {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
    }}

    .tab-row {{
      display: flex;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid var(--border);
      background: rgba(12,14,26,0.85);
      backdrop-filter: blur(8px);
    }}
    .tab-btn {{
      padding: 8px 14px;
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      color: var(--text-dim);
      background: transparent;
      border: none;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .tab-btn.active {{
      background: var(--grad);
      color: #fff;
    }}
    .tab-btn.active.loss-mode {{
      background: var(--grad-loss);
    }}

    .period-row {{
      display: flex;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid rgba(124,47,255,0.15);
      background: rgba(8,9,20,0.9);
    }}
    .period-btn {{
      padding: 6px 12px;
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 700;
      color: var(--text-dim);
      background: transparent;
      border: none;
      cursor: pointer;
      transition: all 0.15s;
      border-bottom: 2px solid transparent;
    }}
    .period-btn.active {{
      color: var(--cyan);
      background: rgba(0,201,177,0.08);
      border-bottom-color: var(--cyan);
    }}
    .period-btn.active.loss-mode {{
      color: var(--red);
      background: rgba(255,47,107,0.08);
      border-bottom-color: var(--red);
    }}

    /* ── Loss banner ── */
    .loss-banner {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 14px;
      padding: 10px 16px;
      border-radius: 8px;
      background: rgba(255,47,107,0.08);
      border: 1px solid rgba(255,47,107,0.25);
      font-family: var(--mono);
      font-size: 11px;
      color: #ff8080;
    }}

    /* ── Section Title ── */
    .section-title {{
      font-family: var(--mono);
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.25em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 20px;
      text-align: center;
    }}

    /* ── Podium ── */
    .podium-wrap {{
      padding: 30px 0 28px;
      border-bottom: 1px solid var(--border);
    }}
    .podium-grid {{
      display: flex;
      justify-content: center;
      align-items: flex-end;
      gap: 36px;
      max-width: 960px;
      margin: 0 auto;
    }}
    .podium-col {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      cursor: pointer;
      transition: transform 0.25s cubic-bezier(0.16,1,0.3,1);
    }}
    .podium-col:hover {{
      transform: translateY(-6px);
    }}

    .trophy-icon-wrap {{
      display: flex;
      align-items: center;
      justify-content: center;
      filter: drop-shadow(0 0 10px rgba(245,200,66,0.35));
    }}
    .trophy-svg {{
      width: 44px;
      height: 44px;
    }}

    .podium-card {{
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-end;
      text-align: center;
      border-radius: 16px;
      box-shadow: 0 0 20px rgba(0,0,0,0.5);
      transition: all 0.25s;
    }}
    .podium-card.rank-1 {{
      width: 230px;
      height: 225px;
      background: linear-gradient(180deg, rgba(245,200,66,0.08) 0%, rgba(12,14,26,0.95) 100%);
      border: 1px solid rgba(245,200,66,0.4);
      padding: 16px 14px;
    }}
    .podium-card.rank-2 {{
      width: 190px;
      height: 185px;
      background: linear-gradient(180deg, rgba(176,184,204,0.06) 0%, rgba(12,14,26,0.95) 100%);
      border: 1px solid rgba(176,184,204,0.3);
      padding: 16px 14px;
    }}
    .podium-card.rank-3 {{
      width: 190px;
      height: 165px;
      background: linear-gradient(180deg, rgba(205,124,58,0.07) 0%, rgba(12,14,26,0.95) 100%);
      border: 1px solid rgba(205,124,58,0.35);
      padding: 16px 14px;
    }}

    .podium-card-stripe {{
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 3px;
      border-radius: 12px 12px 0 0;
    }}
    .rank-1 .podium-card-stripe {{ background: linear-gradient(90deg, #f5c842aa, #f5c842); }}
    .rank-2 .podium-card-stripe {{ background: linear-gradient(90deg, #b0b8ccaa, #b0b8cc); }}
    .rank-3 .podium-card-stripe {{ background: linear-gradient(90deg, #cd7c3aaa, #cd7c3a); }}

    .podium-rank-badge {{
      position: absolute;
      top: -11px; right: -8px;
      width: 24px; height: 24px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 800;
      color: #0a0b0f;
    }}
    .rank-1 .podium-rank-badge {{ background: linear-gradient(135deg,#c9a22a,#f5c842); box-shadow: 0 0 10px rgba(245,200,66,0.6); }}
    .rank-2 .podium-rank-badge {{ background: linear-gradient(135deg,#8a94a6,#b0b8cc); box-shadow: 0 0 10px rgba(176,184,204,0.6); }}
    .rank-3 .podium-rank-badge {{ background: linear-gradient(135deg,#a0612c,#cd7c3a); box-shadow: 0 0 10px rgba(205,124,58,0.6); }}

    .podium-label-tag {{
      position: absolute;
      top: 10px; left: 12px;
      font-family: var(--mono);
      font-size: 8px;
      font-weight: 800;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      opacity: 0.85;
    }}
    .rank-1 .podium-label-tag {{ color: var(--gold); }}
    .rank-2 .podium-label-tag {{ color: var(--silver); }}
    .rank-3 .podium-label-tag {{ color: var(--bronze); }}

    .podium-avatar {{
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--mono);
      font-weight: 700;
      color: #0a0b0f;
      margin-bottom: 8px;
    }}
    .rank-1 .podium-avatar {{ width: 48px; height: 48px; font-size: 15px; background: linear-gradient(135deg,#c9a22a,#f5c842); box-shadow: 0 0 14px rgba(245,200,66,0.5); }}
    .rank-2 .podium-avatar {{ width: 40px; height: 40px; font-size: 12px; background: linear-gradient(135deg,#8a94a6,#b0b8cc); box-shadow: 0 0 12px rgba(176,184,204,0.5); }}
    .rank-3 .podium-avatar {{ width: 40px; height: 40px; font-size: 12px; background: linear-gradient(135deg,#a0612c,#cd7c3a); box-shadow: 0 0 12px rgba(205,124,58,0.5); }}

    .podium-name {{
      font-weight: 700;
      color: var(--text-mid);
      letter-spacing: 0.03em;
      width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-bottom: 3px;
    }}
    .rank-1 .podium-name {{ font-size: 13px; }}
    .rank-2 .podium-name, .rank-3 .podium-name {{ font-size: 11px; }}

    .podium-val {{
      font-family: var(--mono);
      font-weight: 800;
    }}
    .rank-1 .podium-val {{ font-size: 15px; color: var(--gold); text-shadow: 0 0 12px rgba(245,200,66,0.6); }}
    .rank-2 .podium-val {{ font-size: 12px; color: var(--silver); text-shadow: 0 0 12px rgba(176,184,204,0.6); }}
    .rank-3 .podium-val {{ font-size: 12px; color: var(--bronze); text-shadow: 0 0 12px rgba(205,124,58,0.6); }}

    .podium-lvl {{
      font-family: var(--mono);
      font-size: 10px;
      color: var(--text-dim);
      margin-top: 2px;
    }}

    /* ── Table Controls Bar ── */
    .table-controls-bar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
      flex-wrap: wrap;
      gap: 12px;
      padding-top: 24px;
    }}
    .table-standing-summary {{
      font-family: var(--mono);
      font-size: 11px;
      color: var(--text-dim);
      font-weight: 600;
    }}

    .limit-selector {{
      display: flex;
      align-items: center;
      gap: 4px;
      background: rgba(12,14,26,0.85);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 3px 4px;
      backdrop-filter: blur(8px);
    }}
    .limit-btn {{
      padding: 4px 10px;
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 700;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      background: transparent;
      color: var(--text-dim);
      transition: all 0.15s;
    }}
    .limit-btn.active {{
      background: var(--grad);
      color: #fff;
    }}
    .limit-btn.active.loss-mode {{
      background: var(--grad-loss);
    }}

    /* ── Table Grid ── */
    .table-header {{
      display: grid;
      grid-template-columns: 3rem 1fr 10rem 10rem 8rem 6rem;
      padding: 8px 16px;
      margin-bottom: 6px;
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--text-muted);
    }}

    .table-rows {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}

    .row-card {{
      position: relative;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid var(--border-subtle);
      background: rgba(12,14,26,0.7);
      backdrop-filter: blur(4px);
      transition: all 0.15s;
      cursor: default;
    }}
    .row-card:hover {{
      background: rgba(18,22,40,0.9);
      transform: scale(1.002);
    }}

    .row-card.is-self {{
      border-color: rgba(0,201,177,0.35);
      background: rgba(0,201,177,0.04);
    }}

    .row-inner {{
      position: relative;
      display: grid;
      grid-template-columns: 3rem 1fr 10rem 10rem 8rem 6rem;
      align-items: center;
      padding: 12px 16px;
    }}

    .row-rank {{
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 700;
      color: var(--text-muted);
    }}
    .row-rank.top-1 {{ color: var(--gold); text-shadow: 0 0 8px rgba(245,200,66,0.5); }}
    .row-rank.top-2 {{ color: var(--silver); text-shadow: 0 0 8px rgba(176,184,204,0.5); }}
    .row-rank.top-3 {{ color: var(--bronze); text-shadow: 0 0 8px rgba(205,124,58,0.5); }}

    .row-player {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }}
    .row-avatar {{
      width: 32px;
      height: 32px;
      border-radius: 50%;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 700;
      background: #13161f;
      color: var(--text-dim);
    }}
    .row-avatar.top-1 {{ background: linear-gradient(135deg,#c9a22a,#f5c842); color: #0a0b0f; box-shadow: 0 0 10px rgba(245,200,66,0.35); }}
    .row-avatar.top-2 {{ background: linear-gradient(135deg,#8a94a6,#b0b8cc); color: #0a0b0f; box-shadow: 0 0 10px rgba(176,184,204,0.35); }}
    .row-avatar.top-3 {{ background: linear-gradient(135deg,#a0612c,#cd7c3a); color: #0a0b0f; box-shadow: 0 0 10px rgba(205,124,58,0.35); }}
    .row-avatar.is-self {{ background: linear-gradient(135deg, #00C9B1, #7B2FFF); color: #0a0b0f; box-shadow: 0 0 10px rgba(0,201,177,0.4); }}

    .row-name {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text-mid);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .row-name.is-self {{
      color: var(--cyan);
    }}
    .you-badge {{
      font-size: 9px;
      font-family: var(--mono);
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 3px;
      background: rgba(0,201,177,0.15);
      color: var(--cyan);
      border: 1px solid rgba(0,201,177,0.3);
    }}

    .row-level {{
      font-family: var(--mono);
      font-size: 10px;
      color: #3a3f52;
    }}

    .row-networth, .row-xp, .row-dynamic {{
      text-align: right;
      font-family: var(--mono);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }}
    .row-networth.active, .row-xp.active {{
      color: var(--text);
      font-weight: 700;
    }}
    .row-networth.inactive, .row-xp.inactive {{
      color: var(--text-muted);
      font-weight: 400;
    }}

    .row-streak {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 3px;
      font-family: var(--mono);
      font-size: 11px;
    }}

    /* ── Your Standing Box (Bottom) ── */
    .your-standing-section {{
      margin-top: 28px;
    }}
    .your-standing-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
      font-family: var(--mono);
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--cyan);
    }}
    .your-standing-card {{
      position: relative;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid rgba(0, 201, 177, 0.45);
      background: linear-gradient(90deg, rgba(0,201,177,0.08) 0%, rgba(12,14,26,0.95) 100%);
      box-shadow: 0 0 25px rgba(0, 201, 177, 0.15), inset 0 0 15px rgba(0, 201, 177, 0.05);
    }}

    .footer-note {{
      text-align: center;
      font-family: var(--mono);
      font-size: 10px;
      color: var(--text-muted);
      margin-top: 28px;
      letter-spacing: 0.08em;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <!-- Header -->
    <header>
      <div class="header-inner">
        <div>
          <div class="season-label" id="season-tag">Season 4 · Week 12</div>
          <h1>Leaderboard</h1>
          <div class="subtitle" id="active-traders-count">Loading traders...</div>
        </div>

        <div class="controls">
          <div class="tab-row" id="metric-tabs">
            <button class="tab-btn active" data-metric="netWorth">NET WORTH</button>
            <button class="tab-btn" data-metric="xp">TOTAL XP</button>
            <button class="tab-btn" data-metric="returns">RETURNS</button>
            <button class="tab-btn" data-metric="losses">LOSSES</button>
          </div>

          <div class="period-row" id="period-row" style="display: none;">
            <button class="period-btn active" data-period="1M">1M</button>
            <button class="period-btn" data-period="3M">3M</button>
            <button class="period-btn" data-period="6M">6M</button>
            <button class="period-btn" data-period="1Y">1Y</button>
          </div>
        </div>
      </div>

      <div class="loss-banner" id="loss-banner" style="display: none;">
        <svg class="lucide lucide-skull" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#FF2F6B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12.5 17-.5-1-.5 1h1z"/><path d="M15 22a1 1 0 0 0 1-1v-1a2 2 0 0 0 1.56-3.25 8 8 0 1 0-11.12 0A2 2 0 0 0 8 20v1a1 1 0 0 0 1 1z"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/></svg>
        <span>Ranked by worst drawdown — #1 = most rekt.</span>
      </div>
    </header>

    <!-- Podium -->
    <div class="podium-wrap">
      <div class="section-title">◆ TOP FINISHERS ◆</div>
      <div class="podium-grid" id="podium-grid"></div>
    </div>

    <!-- Table -->
    <div class="table-controls-bar">
      <div class="table-standing-summary" id="standing-summary"></div>
      <div class="limit-selector" id="limit-selector">
        <span style="font-family: var(--mono); font-size: 9px; font-weight: 700; color: var(--text-dim); padding: 0 6px; letter-spacing: 0.08em;">VIEW:</span>
        <button class="limit-btn" data-limit="10">Top 10</button>
        <button class="limit-btn" data-limit="50">Top 50</button>
        <button class="limit-btn active" data-limit="100">Top 100</button>
        <button class="limit-btn" data-limit="200">Top 200</button>
      </div>
    </div>

    <div class="table-header">
      <span>#</span>
      <span>Player</span>
      <span style="text-align: right;">Net Worth</span>
      <span style="text-align: right;">Total XP</span>
      <span style="text-align: right;" id="col-dyn-label">24h Chg</span>
      <span style="text-align: right;">Streak</span>
    </div>

    <div class="table-rows" id="table-rows"></div>

    <!-- Your Standing Box -->
    <div class="your-standing-section" id="your-standing-container"></div>

    <div class="footer-note">
      Rankings reset every Sunday at 00:00 UTC · Season 4 ends in 18 days
    </div>
  </div>

  <script>
    const PLAYERS = {players_json};
    const CURRENT_USER = {active_user_json};

    let currentMetric = "netWorth";
    let currentPeriod = "1M";
    let currentLimit = 100;

    const CROWN_SVG = `<svg class="lucide lucide-crown trophy-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f5c842" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/></svg>`;
    const SILVER_MEDAL_SVG = `<svg class="lucide lucide-medal trophy-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#b0b8cc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.12 2.2"/><path d="m13 12 5.88-9.8"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/></svg>`;
    const BRONZE_MEDAL_SVG = `<svg class="lucide lucide-medal trophy-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#cd7c3a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.12 2.2"/><path d="m13 12 5.88-9.8"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/></svg>`;
    const FLAME_SVG = `<svg class="lucide lucide-flame" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#e8a02a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3q1 4 4 6.5t3 5.5a1 1 0 0 1-14 0 5 5 0 0 1 1-3 1 1 0 0 0 5 0c0-2-1.5-3-1.5-5q0-2 2.5-4"/></svg>`;

    function fmtMoney(n) {{
      if (n >= 1e6) return `₹${{(n/1e6).toFixed(2)}}M`;
      if (n >= 1e3) return `₹${{(n/1e3).toFixed(1)}}K`;
      return `₹${{n}}`;
    }}
    function fmtXP(n) {{
      return n >= 1e3 ? `${{(n/1e3).toFixed(1)}}K` : `${{n}}`;
    }}
    function fmtRet(n) {{
      return `${{n >= 0 ? "+" : ""}}${{n.toFixed(1)}}%`;
    }}
    function fmtLoss(n) {{
      return `${{n.toFixed(1)}}%`;
    }}

    function getSortValue(p) {{
      if (currentMetric === "returns") return p.returns[currentPeriod] || 0;
      if (currentMetric === "losses") return p.losses[currentPeriod] || 0;
      return p[currentMetric] || 0;
    }}

    function getDynamic(p) {{
      if (currentMetric === "losses") return {{ text: fmtLoss(p.losses[currentPeriod] || 0), color: "#FF2F6B" }};
      if (currentMetric === "returns") {{
        const v = p.returns[currentPeriod] || 0;
        return {{ text: fmtRet(v), color: v >= 0 ? "#00C9B1" : "#f87171" }};
      }}
      const pos = (p.change24h || 0) >= 0;
      return {{ text: `${{pos ? "+" : ""}}${{(p.change24h || 0).toFixed(1)}}%`, color: pos ? "#00C9B1" : "#f87171" }};
    }}

    function renderAll() {{
      const isLoss = currentMetric === "losses";
      const hasPeriod = currentMetric === "returns" || currentMetric === "losses";

      // Period and loss banner visibility
      document.getElementById("period-row").style.display = hasPeriod ? "flex" : "none";
      document.getElementById("loss-banner").style.display = isLoss ? "flex" : "none";
      document.getElementById("season-tag").className = isLoss ? "season-label loss-mode" : "season-label";

      // Dynamic column header
      const colLabel = document.getElementById("col-dyn-label");
      if (currentMetric === "returns") {{
        colLabel.textContent = `Ret ${{currentPeriod}}`;
        colLabel.style.color = "#00C9B1";
      }} else if (currentMetric === "losses") {{
        colLabel.textContent = `Loss ${{currentPeriod}}`;
        colLabel.style.color = "#FF2F6B";
      }} else {{
        colLabel.textContent = "24h Chg";
        colLabel.style.color = "#2e3347";
      }}

      // Sort players
      const sorted = [...PLAYERS].sort((a, b) =>
        isLoss ? getSortValue(a) - getSortValue(b) : getSortValue(b) - getSortValue(a)
      );

      document.getElementById("active-traders-count").textContent = `${{sorted.length}} active traders · Updated just now`;
      document.getElementById("standing-summary").innerHTML = `STANDINGS <span style="color: #7B2FFF; margin: 0 4px;">/</span> Showing top ${{Math.min(currentLimit, sorted.length)}} of ${{sorted.length}} players`;

      // 1. Render Podium (2nd | 1st | 3rd)
      const p1 = sorted[0];
      const p2 = sorted[1];
      const p3 = sorted[2];

      function renderPodiumCard(p, rank, label, trophySvg) {{
        if (!p) return "";
        const dyn = getDynamic(p);
        const valText = currentMetric === "netWorth" ? fmtMoney(p.netWorth)
                      : currentMetric === "xp" ? `${{fmtXP(p.xp)}} XP`
                      : dyn.text;

        return `
          <div class="podium-col">
            <div class="trophy-icon-wrap">${{trophySvg}}</div>
            <div class="podium-card rank-${{rank}}">
              <div class="podium-card-stripe"></div>
              <div class="podium-rank-badge">${{rank}}</div>
              <div class="podium-label-tag">${{label}}</div>
              <div class="podium-avatar">${{p.avatar}}</div>
              <div class="podium-name">${{p.username}}</div>
              <div class="podium-val">${{valText}}</div>
              <div class="podium-lvl">Lv.${{p.level}}</div>
            </div>
          </div>
        `;
      }}

      const podiumHtml = `
        ${{renderPodiumCard(p2, 2, "RUNNER UP", SILVER_MEDAL_SVG)}}
        ${{renderPodiumCard(p1, 1, "CHAMPION", CROWN_SVG)}}
        ${{renderPodiumCard(p3, 3, "BRONZE", BRONZE_MEDAL_SVG)}}
      `;
      document.getElementById("podium-grid").innerHTML = podiumHtml;

      // 2. Render Table Rows
      const displayed = sorted.slice(0, currentLimit);
      const rowsHtml = displayed.map((p, idx) => {{
        const rank = idx + 1;
        const isSelf = p.username === CURRENT_USER;
        const isTop3 = rank <= 3;
        const topClass = isTop3 ? `top-${{rank}}` : "";
        const dyn = getDynamic(p);

        return `
          <div class="row-card ${{isSelf ? 'is-self' : ''}}">
            <div class="row-inner">
              <span class="row-rank ${{topClass}}">${{rank}}</span>
              <div class="row-player">
                <div class="row-avatar ${{topClass}} ${{isSelf ? 'is-self' : ''}}">${{p.avatar}}</div>
                <div>
                  <div class="row-name ${{isSelf ? 'is-self' : ''}}">
                    ${{p.username}}
                    ${{isSelf ? '<span class="you-badge">YOU</span>' : ''}}
                  </div>
                  <div class="row-level">Lv.${{p.level}}</div>
                </div>
              </div>
              <span class="row-networth ${{currentMetric === 'netWorth' ? 'active' : 'inactive'}}">${{fmtMoney(p.netWorth)}}</span>
              <span class="row-xp ${{currentMetric === 'xp' ? 'active' : 'inactive'}}">${{fmtXP(p.xp)}} XP</span>
              <span class="row-dynamic" style="color: ${{dyn.color}};">${{dyn.text}}</span>
              <div class="row-streak">
                ${{p.streak > 0 ? `${{FLAME_SVG}}<span style="color: #e8a02a; font-weight: 600;">${{p.streak}}d</span>` : '<span style="color: #2e3347;">—</span>'}}
              </div>
            </div>
          </div>
        `;
      }}).join("");
      document.getElementById("table-rows").innerHTML = rowsHtml;

      // 3. Render Your Standing Box
      const selfPlayer = sorted.find(p => p.username === CURRENT_USER) || sorted[0];
      const selfRank = sorted.findIndex(p => p.username === selfPlayer.username) + 1;
      const selfDyn = getDynamic(selfPlayer);

      const yourStandingHtml = `
        <div class="your-standing-header">
          <span>◆ YOUR STANDING ◆</span>
          <div style="flex: 1; height: 1px; background: linear-gradient(90deg, rgba(0,201,177,0.35), transparent);"></div>
        </div>
        <div class="your-standing-card">
          <div class="row-inner">
            <span class="row-rank" style="color: var(--cyan); font-size: 14px; font-weight: 800; text-shadow: 0 0 10px rgba(0,201,177,0.6);">#${{selfRank}}</span>
            <div class="row-player">
              <div class="row-avatar is-self">${{selfPlayer.avatar}}</div>
              <div>
                <div class="row-name is-self" style="font-weight: 700; color: #fff;">
                  ${{selfPlayer.username}}
                  <span class="you-badge">YOU</span>
                </div>
                <div class="row-level">Lv.${{selfPlayer.level}}</div>
              </div>
            </div>
            <span class="row-networth ${{currentMetric === 'netWorth' ? 'active' : 'inactive'}}" style="${{currentMetric === 'netWorth' ? 'color: var(--cyan); font-weight: 700;' : ''}}">${{fmtMoney(selfPlayer.netWorth)}}</span>
            <span class="row-xp ${{currentMetric === 'xp' ? 'active' : 'inactive'}}" style="${{currentMetric === 'xp' ? 'color: var(--cyan); font-weight: 700;' : ''}}">${{fmtXP(selfPlayer.xp)}} XP</span>
            <span class="row-dynamic" style="color: ${{selfDyn.color}}; font-weight: 700;">${{selfDyn.text}}</span>
            <div class="row-streak">
              ${{selfPlayer.streak > 0 ? `${{FLAME_SVG}}<span style="color: #e8a02a; font-weight: 600;">${{selfPlayer.streak}}d</span>` : '<span style="color: #4b5163;">—</span>'}}
            </div>
          </div>
        </div>
      `;
      document.getElementById("your-standing-container").innerHTML = yourStandingHtml;
    }}

    // Metric buttons
    document.querySelectorAll(".tab-btn").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active", "loss-mode"));
        btn.classList.add("active");
        if (btn.dataset.metric === "losses") btn.classList.add("loss-mode");
        currentMetric = btn.dataset.metric;
        renderAll();
      }});
    }});

    // Period buttons
    document.querySelectorAll(".period-btn").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".period-btn").forEach(b => b.classList.remove("active", "loss-mode"));
        btn.classList.add("active");
        if (currentMetric === "losses") btn.classList.add("loss-mode");
        currentPeriod = btn.dataset.period;
        renderAll();
      }});
    }});

    // Limit buttons
    document.querySelectorAll(".limit-btn").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".limit-btn").forEach(b => b.classList.remove("active", "loss-mode"));
        btn.classList.add("active");
        if (currentMetric === "losses") btn.classList.add("loss-mode");
        currentLimit = parseInt(btn.dataset.limit);
        renderAll();
      }});
    }});

    // Initialize
    renderAll();
  </script>
</body>
</html>
"""

def render(user_info):
    """
    Renders the Leaderboard tab using the bundled 'Enhance UI with
    Animation' React leaderboard, injected with real player data.
    """
    players = get_leaderboard_players()
    active_username = user_info.get("username", "krish_surne")

    here = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(here, "standalone_leaderboard.html")

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    data_script = f"""
    <script>
      window.__QUEST_PLAYERS__ = {json.dumps(players)};
      window.__QUEST_CURRENT_USER__ = {json.dumps(active_username)};
    </script>
    """
    html_content = html_content.replace("<head>", "<head>" + data_script, 1)

    components.html(html_content, height=1400, scrolling=True)
