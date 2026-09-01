import sys
import os
import re
import html
import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import time
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings, get_predictions
import nse_live as _nse



def _render_html_table(rows):
    if not rows:
        return ""
    html_out = ['<table style="width:100%;border-collapse:collapse;margin:8px 0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:8px;overflow:hidden;">']
    is_header = True
    for r in rows:
        cells = [c.strip() for c in r.strip('|').split('|')]
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            is_header = False
            continue
        html_out.append('<tr>')
        for c in cells:
            tag = 'th' if is_header else 'td'
            style = 'padding:6px 10px;border:1px solid rgba(255,255,255,0.08);font-size:0.82rem;'
            if is_header:
                style += 'background:rgba(139,92,246,0.18);color:#c084fc;font-weight:700;text-align:left;'
            else:
                style += 'color:#e2e8f0;line-height:1.4;'
            c_fmt = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c)
            html_out.append(f'<{tag} style="{style}">{c_fmt}</{tag}>')
        html_out.append('</tr>')
        if is_header:
            is_header = False
    html_out.append('</table>')
    return "".join(html_out)


def _format_ai_response_html(raw_text: str) -> str:
    if not raw_text:
        return ""
    
    # 1. Normalize excessive newlines (collapse multi-line gaps)
    text = raw_text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 2. Extract and format markdown tables
    lines = text.split('\n')
    out_lines = []
    in_table = False
    table_rows = []
    
    for line in lines:
        s_line = line.strip()
        if s_line.startswith('|') and s_line.endswith('|'):
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(s_line)
        else:
            if in_table:
                out_lines.append(_render_html_table(table_rows))
                in_table = False
                table_rows = []
            out_lines.append(line)
    if in_table:
        out_lines.append(_render_html_table(table_rows))
        
    formatted = '\n'.join(out_lines)
    
    # 3. Format headers (### / ## / #)
    formatted = re.sub(r'^(?:#{1,3})\s+(.+)$', r'<div style="font-weight:700;font-size:0.96rem;color:#f8fafc;margin:8px 0 3px;">\1</div>', formatted, flags=re.MULTILINE)
    
    # Numbered step emojis (1️⃣, 2️⃣, 3️⃣ or 1., 2.)
    formatted = re.sub(r'^([0-9]+[️⃣\.\)]\s*.+)$', r'<div style="font-weight:700;font-size:0.95rem;color:#c084fc;margin:8px 0 3px;">\1</div>', formatted, flags=re.MULTILINE)
    
    # 4. Bold text
    formatted = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#f1f5f9;">\1</strong>', formatted)
    
    # 5. Bullets
    formatted = re.sub(r'^[•\-\*]\s+(.+)$', r'<div style="margin:2px 0 2px 8px;color:#cbd5e1;display:flex;gap:6px;"><span style="color:#a855f7;">•</span><span>\1</span></div>', formatted, flags=re.MULTILINE)
    
    # 6. Paragraphs
    paragraphs = formatted.split('\n\n')
    p_html = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<div') or p.startswith('<table'):
            p_html.append(p)
        else:
            p_clean = p.replace('\n', '<br>')
            p_html.append(f'<div style="margin-bottom:6px;line-height:1.5;color:#cbd5e1;">{p_clean}</div>')
            
    return "".join(p_html)


def render(df=None, summary=None, current_assets=None, _user_info=None,
           portfolio_sentiment_score=None, _sentiment_neg_count=None, comp_score=None):
    total_invested = df['Invested (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl = df['P&L (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    try:
        total_val = summary['total_value']
    except Exception:
        total_val = 0.0

    # ── Styles ────────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .m-header {
        background: linear-gradient(135deg,rgba(99,102,241,.12),rgba(168,85,247,.08));
        border:1px solid rgba(99,102,241,.25);
        border-left:4px solid #818cf8;
        border-radius:14px;
        padding:1.4rem 1.8rem;
        margin-bottom:1.4rem;
    }
    .m-header h2 {
        margin:0 0 .3rem 0;font-size:1.6rem;font-weight:500;
        color:var(--q-text);
        font-family:Inter,sans-serif;
    }
    .m-header p{margin:0;color:var(--q-text-3);font-size:.9rem}
    .cu{display:flex;justify-content:flex-end;margin:.7rem 0}
    .cu-b{background:var(--q-accent-weak);border:1px solid var(--q-accent);
          border-radius:18px 18px 4px 18px;padding:.75rem 1.1rem;
          max-width:72%;color:var(--q-text);font-size:.95rem;line-height:1.5}
    .cm{display:flex;justify-content:flex-start;margin:.7rem 0}
    .cm-w{max-width:78%}
    .cm-lbl{font-size:.72rem;font-family:"JetBrains Mono",monospace;color:var(--q-accent);
            font-weight:500;letter-spacing:1.5px;margin-bottom:4px;padding-left:4px}
    .cm-b{background:var(--q-surface-2);border:1px solid var(--q-border);
          border-radius:4px 18px 18px 18px;padding:.85rem 1.1rem;
          color:var(--q-text-2);font-size:.95rem;line-height:1.6;white-space:normal}
    .cm-ts{font-size:.68rem;color:var(--q-text-3);margin-top:4px;padding-left:4px;
           font-family:"JetBrains Mono",monospace}
    .ti{display:flex;align-items:center;gap:5px;padding:.6rem 1rem}
    .td{width:7px;height:7px;border-radius:50%;background:var(--q-accent);
        animation:tb 1.2s infinite ease-in-out}
    .td:nth-child(2){animation-delay:.2s}
    .td:nth-child(3){animation-delay:.4s}
    @keyframes tb{0%,80%,100%{transform:scale(.7);opacity:.5}40%{transform:scale(1.1);opacity:1}}
    .m-notice{font-size:.78rem;color:#64748b;margin-top:4px}
    </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="m-header">
      <h2>⚡ MICHAEL</h2>
      <p>Portfolio Intelligence Assistant &nbsp;&middot;&nbsp; Quantitative Unified Equity Surveillance Tracker</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    import json as _mcj, os as _mco
    _mchat_file = _mco.path.join(st.session_state.get("_quest_data_dir", "."), "michael_chat.json")

    def _m_persist():
        try:
            with open(_mchat_file, "w", encoding="utf-8") as _f:
                _mcj.dump(st.session_state.michael_history[-100:], _f, indent=2)
        except Exception:
            pass

    if "michael_history" not in st.session_state:
        # Load persisted conversation from the user's folder (memory across sessions)
        try:
            with open(_mchat_file, encoding="utf-8") as _f:
                st.session_state.michael_history = _mcj.load(_f)
        except Exception:
            st.session_state.michael_history = []
    if "michael_api_key" not in st.session_state:
        st.session_state.michael_api_key = ""
    if "michael_pending" not in st.session_state:
        st.session_state.michael_pending = None

    # ── Provider/key resolution: shared key (from secrets) first, user override second
    def _provider_of(k):
        return "groq" if k.startswith("gsk_") else "gemini"

    _shared_key = ""
    try:
        _shared_key = (str(st.secrets.get("GROQ_API_KEY", "")).strip()
                       or str(st.secrets.get("GEMINI_API_KEY", "")).strip())
    except Exception:
        _shared_key = ""

    if _shared_key:
        api_key = _shared_key
        provider = _provider_of(_shared_key)
        st.caption("⚡ MICHAEL is powered for you — no key needed.")
        with st.expander("Advanced · use your own key"):
            rk = st.text_input("Your Groq (gsk_…, free) or Gemini key", type="password",
                               value=st.session_state.michael_api_key,
                               key="michael_key_input", label_visibility="collapsed")
            if rk != st.session_state.michael_api_key:
                st.session_state.michael_api_key = rk
            if st.session_state.michael_api_key.strip():
                api_key = st.session_state.michael_api_key.strip()
                provider = _provider_of(api_key)
    else:
        key_set = bool(st.session_state.michael_api_key.strip())
        with st.expander("🔑 AI API Key" + (" ✅" if key_set else " — required"), expanded=not key_set):
            rk = st.text_input("Groq (gsk_…, free) or Gemini key", type="password",
                               value=st.session_state.michael_api_key,
                               key="michael_key_input", placeholder="gsk_...",
                               label_visibility="collapsed")
            if rk != st.session_state.michael_api_key:
                st.session_state.michael_api_key = rk
            st.markdown('<div class="m-notice">🔒 Never saved to disk or logged. '
                        'Get a free Groq key at console.groq.com.</div>', unsafe_allow_html=True)
        api_key = st.session_state.michael_api_key.strip()
        provider = _provider_of(api_key) if api_key else "gemini"

    # ── Context builder (compact — target < 1000 tokens) ─────────────────────
    def _m_context():
        import datetime as _dt
        L = []

        # Section 1: Portfolio summary — totals + top 3 gainers/losers only
        L.append("=== PORTFOLIO SUMMARY ===")
        if not df.empty:
            tv   = summary.get("total_value", 0)
            icol = "Invested (₹)" if "Invested (₹)" in df.columns else "Invested"
            pcol = "P&L (₹)"      if "P&L (%)" in df.columns else "P&L"
            ppcol= "P&L %"        if "P&L %" in df.columns else "P&L %"
            ti   = df[icol].sum() if icol in df.columns else 0
            tp   = df[pcol].sum() if pcol in df.columns else 0
            tpp  = (tp / ti * 100) if ti > 0 else 0
            rs   = summary.get("portfolio_risk_score", 0)
            rb   = summary.get("portfolio_risk_bucket", "?")
            L += [
                f"Value: Rs.{tv:,.2f} | Invested: Rs.{ti:,.2f} | P&L: Rs.{tp:+,.2f} ({tpp:+.2f}%)",
                f"Risk: {rs:.1f}/100 ({rb})",
            ]
            if ppcol in df.columns:
                sorted_df = df.sort_values(ppcol, ascending=False)
                top3    = sorted_df.head(3)
                bottom3 = sorted_df.tail(3)
                L.append("Top 3 gainers:")
                for _, r in top3.iterrows():
                    L.append(f"  {r['Name']}: {r.get(ppcol,0):+.2f}% (Rs.{r.get(pcol,0):+,.2f})")
                L.append("Top 3 losers:")
                for _, r in bottom3.iterrows():
                    L.append(f"  {r['Name']}: {r.get(ppcol,0):+.2f}% (Rs.{r.get(pcol,0):+,.2f})")
        else:
            L.append("No data.")

        # Section 2: EWMA state — last 2 learning entries only
        L += ["", "=== EWMA STATE ==="]
        try:
            from adaptive_engine import _load_state as _ae
            ae = _ae()
            ll = ae.get("learning_log", [])
            L += [
                f"mu_ewma: Rs.{ae.get('mu_ewma','?')} | sigma_ewma: Rs.{ae.get('sigma_ewma','?')}",
                f"days_trained: {ae.get('days_trained',0)} | bias_5d: Rs.{ll[-1].get('bias_5d',0):+.4f}" if ll else "days_trained: 0",
            ]
            if ll:
                L.append("Last 2 learning entries:")
                for e in ll[-2:]:
                    L.append(f"  {e['date']} ret=Rs.{e['actual_return']:+,.2f} mu:{e['mu_old']:+.2f}->{e['mu_new']:+.2f} err=Rs.{e['error']:+,.2f}")
        except Exception:
            L.append("EWMA unavailable.")

        # Section 3: Predictions — last 3 only
        L += ["", "=== RECENT PREDICTIONS (last 3) ==="]
        preds = get_predictions()
        for p in sorted(preds, key=lambda x: x["target_date"])[-3:]:
            act = f"Rs.{p['real_val']:,.2f}" if p.get("real_val") else "Pending"
            err = f"Rs.{(p['real_val']-p['expected_val']):+,.2f}" if p.get("real_val") else "-"
            L.append(f"  {p['target_date']} exp=Rs.{p['expected_val']:,.2f} act={act} err={err}")

        # Section 4: News — sentiment label + score only, no headlines
        L += ["", "=== NEWS SENTIMENT ==="]
        try:
            from news_sentiment import get_archived_articles as _ga
            arch = _ga()
            for a in current_assets:
                if not a.identifier: continue
                arts = [x for x in arch.get(a.identifier, []) if x.get("sentiment_score", 0) != 0]
                if arts:
                    sc = sum(x["sentiment_score"] for x in arts[:5]) / min(5, len(arts))
                    lb = "Bullish" if sc > 0.15 else "Bearish" if sc < -0.15 else "Neutral"
                    L.append(f"  {a.name}: {lb} ({sc:+.3f})")
        except Exception:
            L.append("News unavailable.")

        # Section 5: System state (holiday-aware)
        L += ["", "=== SYSTEM STATE ==="]
        now = _dt.datetime.now()
        try:
            import nse_live as _nsl
            L.append(f"{now.strftime('%Y-%m-%d %H:%M')} IST | Market: {_nsl.get_market_status()}")
            _tom = (now + _dt.timedelta(days=1)).date()
            _nd = _tom
            for _ in range(10):
                if _nd.weekday() < 5 and not _nsl.is_nse_holiday(_nd):
                    break
                _nd = _nd + _dt.timedelta(days=1)
            if _tom.weekday() >= 5 or _nsl.is_nse_holiday(_tom):
                _why = "weekend" if _tom.weekday() >= 5 else _nsl.get_holiday_calendar().get(_tom.strftime('%Y-%m-%d'), 'holiday')
                L.append(f"IMPORTANT: tomorrow ({_tom}) is NOT a trading day ({_why}). "
                         f"Do not give a next-day prediction for it. Next trading day: {_nd}.")
        except Exception:
            mkt = now.weekday() < 5 and (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 30))
            L.append(f"{now.strftime('%Y-%m-%d %H:%M')} IST | Market: {'OPEN' if mkt else 'CLOSED'}")
        pending = [p for p in preds if not p.get("real_val")]
        if pending:
            L.append(f"Latest stored prediction target: {pending[0]['target_date']} "
                     f"Rs.{pending[0]['expected_val']:,.2f} (only meaningful on a trading day).")

        # Section 6: Planner — upcoming events + open to-do tasks
        L += ["", "=== PLANNER (calendar + to-do) ==="]
        try:
            import json as _mj, os as _mo
            _mpd = st.session_state.get("_quest_data_dir", ".")
            try:
                with open(_mo.path.join(_mpd, "events.json"), encoding="utf-8") as _mf:
                    _m_evs = _mj.load(_mf)
            except Exception:
                _m_evs = []
            try:
                with open(_mo.path.join(_mpd, "tasks.json"), encoding="utf-8") as _mf:
                    _m_tks = _mj.load(_mf)
            except Exception:
                _m_tks = []
            _tstr = _dt.date.today().strftime("%Y-%m-%d")
            _up = sorted([e for e in _m_evs if e.get("date", "") >= _tstr], key=lambda x: x.get("date", ""))[:5]
            if _up:
                L.append("Upcoming events:")
                for e in _up:
                    L.append(f"  {e.get('date')}: {e.get('title')}" + (f" — {e.get('note')}" if e.get('note') else ""))
            else:
                L.append("No upcoming events.")
            _open_t = [t for t in _m_tks if not t.get("done")]
            if _open_t:
                L.append(f"Open tasks ({len(_open_t)}):")
                for t in _open_t[:8]:
                    L.append(f"  [ ] {t.get('text')}")
            else:
                L.append("No open tasks.")
        except Exception:
            L.append("Planner unavailable.")

        ctx = "\n".join(L)
        print(f"[MICHAEL] Context size: {len(ctx)} chars / ~{len(ctx)//4} tokens", file=sys.stderr)
        return ctx

    # ── Gemini call — auto-probes model names until one works ─────────────────
    _GEMINI_MODELS = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-pro-latest",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-pro",
    ]
    _GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def _m_gemini(key, q, ctx):
        import urllib.request, json as _j
        SYS = (
            "You are MICHAEL, the daily intelligence assistant inside QUEST — a personal "
            "investing + planning app for an Indian retail investor. "
            "You can see the user's live portfolio, risk metrics, predictions, news sentiment, "
            "AND their planner: upcoming calendar events and open to-do tasks. "
            "Behave like a proactive personal assistant: connect their schedule to their money — "
            "flag upcoming results/holidays, remind them of open tasks, relate market events to their holdings, "
            "and suggest what to focus on today. "
            "You are knowledgeable about Indian markets, NSE/BSE stocks, ETFs, and quantitative finance. "
            "PERSONALITY: you are a sharp, seasoned Mumbai trading-desk veteran — quick-witted, a little blunt, "
            "with dry humour, but genuinely in the user's corner. Open with one short line that fits the time of "
            "day and the market mood, then get to the point. Direct and honest — never sugarcoat bad news, but never preachy. "
            "Ground every answer in the data provided. Never invent numbers. "
            "Keep responses concise, short paragraphs, Rs. for rupees, plain text (no markdown headers)."
        )
        # Recent conversation for continuity (last few turns, excluding the current question)
        _hist = st.session_state.get("michael_history", [])
        _convo = ""
        for _hm in _hist[-7:-1]:
            _convo += f"{'User' if _hm.get('role') == 'user' else 'MICHAEL'}: {_hm.get('text','')}\n"
        full = f"{SYS}\n\n--- CONTEXT ---\n{ctx}\n--- END ---\n\n{_convo}User: {q}\nMICHAEL:"
        payload = _j.dumps({
            "contents": [{"parts": [{"text": full}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }).encode()

        # Use cached working model if already discovered this session
        models_to_try = (
            [st.session_state["_michael_model"]]
            if "_michael_model" in st.session_state
            else _GEMINI_MODELS
        )

        last_error = "No models attempted."
        for model in models_to_try:
            url = f"{_GEMINI_BASE}/{model}:generateContent?key={key}"
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    res = _j.loads(r.read().decode())
                # Cache this model so we don't probe on every message
                st.session_state["_michael_model"] = model
                print(f"[MICHAEL] Using model: {model}", file=sys.stderr)
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                print(f"[MICHAEL] HTTP {e.code} for model '{model}': {body}", file=sys.stderr)
                if e.code in (400, 403):
                    return "__BAD_KEY__"
                # 429 or 404 — try the next model before giving up
                last_error = f"HTTP {e.code}: {body[:400]}"
                continue
            except Exception as ex:
                print(f"[MICHAEL] Exception for model '{model}': {ex}", file=sys.stderr)
                last_error = str(ex)
                continue

        # All models exhausted — return the last error body so user can diagnose
        return f"__RATE_LIMIT__ {last_error}"

    # ── Live-data tools MICHAEL can call on demand ────────────────────────────
    def _tool_quote(query):
        import urllib.request as _U, urllib.parse as _P, json as _J, yfinance as _yf2
        try:
            u = "https://query2.finance.yahoo.com/v1/finance/search?q=" + _P.quote(str(query))
            with _U.urlopen(_U.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=5) as r:
                qs = _J.load(r).get("quotes", [])
            sym = None
            for suf in (".NS", ".BO"):
                for q2 in qs:
                    if str(q2.get("symbol", "")).endswith(suf):
                        sym = q2["symbol"]; break
                if sym:
                    break
            if not sym and qs:
                sym = qs[0].get("symbol")
            if not sym:
                return _J.dumps({"error": f"no ticker found for '{query}'"})
            h = _yf2.Ticker(sym).history(period="1y")["Close"].dropna()
            if len(h) < 2:
                return _J.dumps({"ticker": sym, "error": "no price data"})
            last = float(h.iloc[-1])
            ret6 = (last / h.iloc[-126] - 1) * 100 if len(h) >= 126 else (last / h.iloc[0] - 1) * 100
            _d = h.diff(); _up = _d.clip(lower=0).rolling(14).mean(); _dn = (-_d.clip(upper=0)).rolling(14).mean()
            _rs = _up / _dn.replace(0, float('nan')); rsi = float((100 - 100 / (1 + _rs)).iloc[-1])
            m50 = h.rolling(50).mean().iloc[-1] if len(h) >= 50 else None
            m200 = h.rolling(200).mean().iloc[-1] if len(h) >= 200 else None
            trend = "golden_cross" if (m50 and m200 and m50 > m200) else ("death_cross" if (m50 and m200) else "n/a")
            hi, lo = h.max(), h.min()
            pos = round((last - lo) / (hi - lo) * 100) if hi > lo else None
            return _J.dumps({"ticker": sym, "price": round(last, 2), "six_month_return_pct": round(ret6, 1),
                             "rsi14": round(rsi), "trend_50_200": trend, "pct_of_52w_range": pos})
        except Exception as e:
            return _J.dumps({"error": str(e)})

    def _tool_index(name):
        import json as _J, yfinance as _yf2
        mp = {"nifty": "^NSEI", "nifty50": "^NSEI", "nifty 50": "^NSEI", "sensex": "^BSESN",
              "bank nifty": "^NSEBANK", "banknifty": "^NSEBANK", "nifty bank": "^NSEBANK"}
        tk = mp.get(str(name).lower().strip(), "^NSEI")
        try:
            fi = _yf2.Ticker(tk).fast_info
            last = float(fi.last_price); prev = float(fi.previous_close)
            return _J.dumps({"index": name, "value": round(last, 2),
                             "day_change_pct": round((last - prev) / prev * 100, 2)})
        except Exception as e:
            return _J.dumps({"error": str(e)})

    _TOOLS = [
        {"type": "function", "function": {
            "name": "get_quote",
            "description": "Get the LIVE price and key technical indicators (RSI, 50/200 trend, 52-week range "
                           "position, 6-month return) for ANY Indian stock by company name or ticker. Use this "
                           "whenever asked about a specific stock's market performance, or to ground a stock "
                           "recommendation in real current data.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Company name or ticker, e.g. 'Reliance' or 'TCS.NS'"}},
                "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "get_index",
            "description": "Get the live value and day change for an Indian market index (NIFTY 50, SENSEX, Bank Nifty).",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Index name: 'NIFTY 50', 'SENSEX', or 'Bank Nifty'"}},
                "required": ["name"]}}},
    ]

    def _m_groq(key, q, ctx):
        import urllib.request, json as _j
        SYS = (
            "You are MICHAEL, the daily intelligence assistant inside QUEST — a personal "
            "investing + planning app for an Indian retail investor. "
            "You can see the user's live portfolio, risk metrics, predictions, news sentiment, and planner "
            "(events + to-dos). You ALSO have live tools: get_quote (real-time price + indicators for any stock) "
            "and get_index (live NIFTY/SENSEX/Bank Nifty). ALWAYS call get_quote or get_index when asked about a "
            "specific stock, an index, or to recommend stocks — never quote prices from memory; fetch them. "
            "When recommending, name candidates then call get_quote on them to ground it in real data, and be clear "
            "these are research ideas, not advice. "
            "PERSONALITY: a sharp, seasoned Mumbai trading-desk veteran — quick-witted, a little blunt, dry humour, "
            "but genuinely in the user's corner. Open with one short line fitting the time of day and market mood, then "
            "get to the point. Direct and honest — never sugarcoat, never preachy. "
            "Ground every answer in the data/tools; never invent numbers. "
            "Concise, short paragraphs, Rs. for rupees, plain text (no markdown headers)."
        )
        msgs = [{"role": "system", "content": SYS + "\n\n--- CONTEXT ---\n" + ctx + "\n--- END ---"}]
        for _hm in st.session_state.get("michael_history", [])[-7:-1]:
            msgs.append({"role": "user" if _hm.get("role") == "user" else "assistant",
                         "content": _hm.get("text", "")})
        msgs.append({"role": "user", "content": q})
        H = {"Content-Type": "application/json", "Authorization": f"Bearer {key}",
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

        def _post(messages, use_tools=True):
            body = {"model": "openai/gpt-oss-120b", "messages": messages,
                    "temperature": 0.6, "max_tokens": 1024}
            if use_tools:
                body["tools"] = _TOOLS
                body["tool_choice"] = "auto"
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                                         data=_j.dumps(body).encode(), headers=H, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                return _j.loads(r.read().decode())

        try:
            m = {}
            for _round in range(12):  # allow more tool round-trips for multiple stocks
                import time as _time
                try:
                    res = _post(msgs, use_tools=True)
                except urllib.error.HTTPError as _te:
                    _tb = _te.read().decode("utf-8", errors="ignore")
                    if _te.code == 429:
                        import re
                        m_wait = re.search(r"try again in ([\d\.]+)s", _tb)
                        wait_t = float(m_wait.group(1)) + 1.0 if m_wait else 8.0
                        print(f"[MICHAEL/groq] Rate limited (429), sleeping {wait_t}s and retrying...", file=sys.stderr)
                        _time.sleep(wait_t)
                        res = _post(msgs, use_tools=True) # Retry once
                    elif _te.code == 400 and "tool_use_failed" in _tb:
                        print("[MICHAEL/groq] tool_use_failed — retrying without tools", file=sys.stderr)
                        res = _post(msgs, use_tools=False)
                    else:
                        raise
                m = res["choices"][0]["message"]
                tcs = m.get("tool_calls")
                if not tcs:
                    return (m.get("content") or "").strip()
                msgs.append({"role": "assistant", "content": m.get("content"), "tool_calls": tcs})
                for tc in tcs:
                    fn = tc.get("function", {}).get("name", "")
                    try:
                        args = _j.loads(tc.get("function", {}).get("arguments") or "{}")
                    except Exception:
                        args = {}
                    if fn == "get_quote":
                        out = _tool_quote(args.get("query", ""))
                    elif fn == "get_index":
                        out = _tool_index(args.get("name", ""))
                    else:
                        out = _j.dumps({"error": "unknown tool"})
                    print(f"[MICHAEL/tool] {fn}({args}) -> {out[:120]}", file=sys.stderr)
                    msgs.append({"role": "tool", "tool_call_id": tc.get("id"), "content": out})
            return (m.get("content") or "I pulled the data but ran out of steps — ask me once more.").strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            print(f"[MICHAEL/groq] HTTP {e.code}: {body}", file=sys.stderr)
            if e.code in (401, 403):
                return "__BAD_KEY__"
            return f"__RATE_LIMIT__ HTTP {e.code}: {body[:300]}"
        except Exception as ex:
            print(f"[MICHAEL/groq] {ex}", file=sys.stderr)
            return f"__RATE_LIMIT__ {ex}"

    def _m_ask(q, ctx):
        return _m_groq(api_key, q, ctx) if provider == "groq" else _m_gemini(api_key, q, ctx)

    # ── Send / process helpers ────────────────────────────────────────────────
    def _m_send(q):
        if not q.strip(): return
        # Per-session rate limit (protects the shared key): 15 msgs / 5 min
        import time as _mt
        _now = _mt.time()
        _hits = [t for t in st.session_state.get("_m_hits", []) if _now - t < 300]
        if len(_hits) >= 15:
            st.session_state.michael_history.append({
                "role": "michael", "ts": datetime.now().strftime("%H:%M"),
                "text": "You've hit the message limit (15 per 5 minutes). Give me a moment, then ask again."})
            return
        _hits.append(_now)
        st.session_state["_m_hits"] = _hits
        ts = datetime.now().strftime("%H:%M")
        st.session_state.michael_history.append({"role": "user", "text": q.strip(), "ts": ts})
        _m_persist()
        st.session_state.michael_pending = q.strip()

    def _m_process():
        q = st.session_state.michael_pending
        if not q: return
        st.session_state.michael_pending = None
        raw = _m_ask(q, _m_context())
        ts = datetime.now().strftime("%H:%M")
        if raw == "__BAD_KEY__":
            txt = ("MICHAEL is unavailable — the API key is invalid or not authorised. "
                   "Check the key in the app's secrets (Groq: console.groq.com).")
        elif raw.startswith("__RATE_LIMIT__"):
            detail = raw[len("__RATE_LIMIT__"):].strip()
            txt = ("MICHAEL hit a snag talking to the AI service (rate limit or a transient error). "
                   "Give it a moment and try again.\n\n"
                   f"Details: {detail}")
        elif raw.startswith("__ERROR__"):
            txt = f"MICHAEL error: {raw[9:].strip()}"
        else:
            txt = raw
        st.session_state.michael_history.append({"role": "michael", "text": txt, "ts": ts})
        _m_persist()

    # ── Main UI ───────────────────────────────────────────────────────────────
    if not api_key:
        st.info("🔑 Please enter your Gemini API key above to activate MICHAEL.")
    else:
        history = st.session_state.michael_history

        if not history:
            # Welcome + starter chips
            st.markdown("""
            <div class="cm">
              <div class="cm-w">
                <div class="cm-lbl">MICHAEL</div>
                <div class="cm-b">I am MICHAEL. I can see your portfolio, your risk, the news, and your planner (events + to-dos). Ask me anything — or get your daily briefing.</div>
                <div class="cm-ts">ready</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            starters = [
                "Give me my daily briefing",
                "What's on my plate today?",
                "Which stock is dragging my portfolio?",
                "Any events or results coming up?",
                "What should I focus on this week?",
            ]
            cols = st.columns(len(starters))
            for i, (c, q) in enumerate(zip(cols, starters)):
                with c:
                    if st.button(q, key=f"m_chip_{i}", use_container_width=True):
                        _m_send(q)
                        st.rerun()
        else:
            # Render history
            for msg in history:
                if msg["role"] == "user":
                    clean_u_text = html.escape(msg["text"]).replace('\n', '<br>')
                    st.markdown(
                        f'<div class="cu"><div class="cu-b">{clean_u_text}</div></div>',
                        unsafe_allow_html=True)
                else:
                    fmt_m_text = _format_ai_response_html(msg["text"])
                    st.markdown(
                        f'<div class="cm"><div class="cm-w">'                        f'<div class="cm-lbl">MICHAEL</div>'                        f'<div class="cm-b">{fmt_m_text}</div>'                        f'<div class="cm-ts">{msg["ts"]}</div></div></div>',
                        unsafe_allow_html=True)
            # Typing indicator
            if st.session_state.michael_pending:
                st.markdown("""
                <div class="cm"><div class="cm-w">
                  <div class="cm-lbl">MICHAEL</div>
                  <div class="cm-b"><div class="ti">
                    <div class="td"></div><div class="td"></div><div class="td"></div>
                  </div></div>
                </div></div>
                """, unsafe_allow_html=True)

        # Process pending (API call)
        if st.session_state.michael_pending:
            _m_process()
            st.rerun()

        # Input bar — form clears the box automatically after sending
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("michael_form", clear_on_submit=True):
            ic, bc = st.columns([5, 1])
            user_input = ic.text_input("Ask MICHAEL", key="michael_input",
                placeholder="Type your question...", label_visibility="collapsed")
            _sent = bc.form_submit_button("Send ⚡", use_container_width=True)
        if _sent and user_input.strip():
            _m_send(user_input)
            st.rerun()

        if st.session_state.michael_history:
            if st.button("🗑 Clear MICHAEL's memory", key="m_clear"):
                st.session_state.michael_history = []
                _m_persist()
                st.rerun()


    # ══════════════════════════════════════════════════════════════════════════════
    # PLANNER — editable calendar + to-do (Overview keeps a read-only quick glance)
    # ══════════════════════════════════════════════════════════════════════════════
