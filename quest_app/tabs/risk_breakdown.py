import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
import plotly.express as px
import plotly.graph_objects as go
import time
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings
import nse_live as _nse


import yfinance as _yf
import urllib.request as _ur, urllib.parse as _up, json as _json

_PMAP = {
    "1D": ("1d", "15m"), "1M": ("1mo", "1d"), "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"), "1Y": ("1y", "1d"), "3Y": ("3y", "1wk"), "5Y": ("5y", "1wk")
}

def _cmp_lookup(name):
    try:
        u = "https://query2.finance.yahoo.com/v1/finance/search?q=" + _up.quote(name.strip())
        rq = _ur.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with _ur.urlopen(rq, timeout=4) as r:
            d = _json.load(r)
        qs = d.get("quotes", [])
        for suf in (".NS", ".BO"):
            for q in qs:
                if str(q.get("symbol", "")).endswith(suf):
                    return q["symbol"]
        return qs[0].get("symbol") if qs else None
    except Exception:
        return None

@st.cache_data(ttl=900, show_spinner=False)
def _cmp_series(ticker, period="6mo"):
    try:
        h = _yf.Ticker(ticker).history(period=period)["Close"].dropna()
        return h if len(h) > 5 else None
    except Exception:
        return None

def _cmp_rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, float('nan'))
    return float((100 - 100 / (1 + rs)).iloc[-1])

@st.cache_data(ttl=900, show_spinner=False)
def _idx_ret(tk):
    s = _cmp_series(tk, "1y")
    if s is None or len(s) < 2:
        return None
    return float((s.iloc[-1] / s.iloc[0] - 1) * 100)

@st.cache_data(ttl=900, show_spinner=False)
def _cmp_fetch(ticker, plbl, start, end):
    try:
        if plbl == "Custom":
            h = _yf.Ticker(ticker).history(start=str(start), end=str(end))
        else:
            _per, _iv = _PMAP.get(plbl, ("6mo", "1d"))
            h = _yf.Ticker(ticker).history(period=_per, interval=_iv)
        h = h.dropna()
        return h if len(h) > 2 else None
    except Exception:
        return None

@st.cache_data(ttl=900, show_spinner=False)
def _cmp_indic(ticker):
    """1-year-based indicators: RSI, 50/200 cross, MACD, 52-week position."""
    out = {}
    try:
        s = _yf.Ticker(ticker).history(period="1y")["Close"].dropna()
        if len(s) < 30:
            return out
        out["rsi"] = _cmp_rsi(s)
        if len(s) >= 200:
            _m50, _m200 = s.rolling(50).mean().iloc[-1], s.rolling(200).mean().iloc[-1]
            out["trend"] = "🟢 Golden" if _m50 > _m200 else "🔴 Death"
        else:
            out["trend"] = "—"
        _e12, _e26 = s.ewm(span=12).mean(), s.ewm(span=26).mean()
        _macd = _e12 - _e26
        _sigl = _macd.ewm(span=9).mean()
        out["macd"] = "🟢 Bull" if _macd.iloc[-1] > _sigl.iloc[-1] else "🔴 Bear"
        _hi, _lo = s.max(), s.min()
        out["pos52"] = round((s.iloc[-1] - _lo) / (_hi - _lo) * 100) if _hi > _lo else None
    except Exception:
        pass
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def _cmp_fund(ticker):
    try:
        info = _yf.Ticker(ticker).info
        return {"pe": info.get("trailingPE"), "mcap": info.get("marketCap"),
                "dy": info.get("dividendYield"), "beta": info.get("beta")}
    except Exception:
        return {}


def render(df=None, summary=None, current_assets=None, _user_info=None,
           portfolio_sentiment_score=None, _sentiment_neg_count=None, comp_score=None):
    total_invested = df['Invested (₹)'].sum() if df is not None and not df.empty else 0.0
    total_pnl = df['P&L (₹)'].sum() if df is not None and not df.empty else 0.0
    total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    try:
        total_val = summary['total_value']
    except Exception:
        total_val = 0.0
        if st.session_state.show_risk_breakdown:
            c_back, _ = st.columns([1, 4])
            if c_back.button("← Back to Dashboard"):
                st.session_state.show_risk_breakdown = False
                st.rerun()
        
            _rtab1, _rtab2 = st.tabs(["📊 Risk Breakdown", "🔬 Compare & Analyze"])
            with _rtab1:
                st.subheader("Composite Risk Score Breakdown")
                if not df.empty and total_invested > 0:
                    # Gauge Chart for Score
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = comp_score,
                        title = {'text': "Overall Risk Score"},
                        gauge = {
                            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': _pal['text_3']},
                            'bar': {'color': _pal['accent'], 'thickness': 0.22},
                            'bgcolor': "rgba(0,0,0,0)",
                            'borderwidth': 1,
                            'bordercolor': _pal['border'],
                            'steps': [
                                {'range': [0, 40], 'color': _pal['pos_weak']},
                                {'range': [40, 70], 'color': _pal['warn_weak']},
                                {'range': [70, 100], 'color': _pal['neg_weak']}],
                            'threshold': {
                                'line': {'color': _pal['text'], 'width': 3},
                                'thickness': 0.75,
                                'value': comp_score}
                        }
                    ))
                    fig_gauge.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), font=dict(family="Inter", color=_pal['text_2']), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    ui_theme.style_fig(fig_gauge)
                    st.plotly_chart(fig_gauge, use_container_width=True)
        
                    # Verdict
                    bucket_color = _pal['pos'] if comp_score <= 40 else _pal['warn'] if comp_score <= 70 else _pal['neg']
                    st.markdown(f"<h4 style='text-align: center; color: {bucket_color}; font-family: \"Inter\", sans-serif;'>Your portfolio carries {summary['portfolio_risk_bucket']} risk. The primary drivers are your highest-scoring components below.</h4>", unsafe_allow_html=True)
                    st.markdown("---")
        
                    def render_component(title, weight, score, text, formula):
                        c_color = _pal['pos'] if score <= 40 else _pal['warn'] if score <= 70 else _pal['neg']
                        contrib = score * (weight/100)
                        return f"""
                        <div style="background: var(--q-surface); border: 1px solid var(--q-border); border-radius: 12px; padding: 1.2rem; height: 100%; margin-bottom: 1rem; font-family: 'Inter', sans-serif;">
                            <h4 style="margin-top: 0; margin-bottom: 0.2rem; color: var(--q-text);">{title}</h4>
                            <p style="color: var(--q-text-3); font-size: 0.8rem; margin-top: 0;">Weight: {weight}% | Contributes {contrib:.1f} pts</p>
                            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                                <div style="flex-grow: 1; background: var(--q-surface-2); height: 8px; border-radius: 4px; overflow: hidden; margin-right: 15px;">
                                    <div class="q-bar" style="width: {score}%; background: {c_color}; height: 100%;"></div>
                                </div>
                                <span style="font-family: 'JetBrains Mono', monospace; font-weight: 500; color: {c_color}; font-size: 1.2rem;">{score:.1f}</span>
                            </div>
                            <p style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.5;">{text}</p>
                            <div style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 0.5rem; margin-top: 1rem;">
                                <code style="color: #38bdf8; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;">{formula}</code>
                            </div>
                        </div>
                        """
            
                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.html(render_component(
                            "Concentration Risk", 22, score_conc,
                            f"Your top asset ({top_asset['Name']}) holds {top_pct:.1f}% of your portfolio. If perfectly equal across {len(df)} assets, each would be {100/len(df):.1f}%.",
                            "HHI = \u03a3(w\u1d62\u00b2) \u00d7 10000"
                        ))

                    with r2:
                        st.html(render_component(
                            "Volatility Risk", 22, score_vol,
                            f"Your portfolio's daily standard deviation is \u20b9{vol_rupees:,.2f} ({vol_daily_pct:.2f}%). On a bad day, expect to move this much.",
                            "\u03c3\u209a = \u221a(w\u1d40\u03a3w)"
                        ))

                    with r3:
                        st.html(render_component(
                            "Drawdown Risk", 17, score_dd,
                            f"Your losing positions ({len(losers)} assets) collectively represent \u20b9{unrealised_loss:,.2f} of unrealised loss.",
                            "Loss Contrib = \u03a3(w\u1d62 \u00d7 |P&amp;L\u1d62|) for P&amp;L &lt; 0"
                        ))

                    r4, r5, r6 = st.columns(3)
                    with r4:
                        st.html(render_component(
                            "Correlation Risk", 12, score_corr,
                            f"Your average inter-asset correlation is {mean_corr:.2f}. A perfectly diversified portfolio would be close to 0.",
                            "Mean Corr = (2 / n(n-1)) \u00d7 \u03a3 \u03c1\u1d62\u2c7c"
                        ))

                    with r5:
                        st.html(render_component(
                            "Momentum Risk", 12, score_mom,
                            f"{mom_count} out of {len(df)} assets are in a negative 1-month trend, representing {mom_weight*100:.1f}% of your portfolio by value.",
                            "Score = % Weight of Assets w/ 1M Ret &lt; 0"
                        ))

                    with r6:
                        _sent_label = "Bullish" if portfolio_sentiment_score > 0.15 else "Bearish" if portfolio_sentiment_score < -0.15 else "Neutral"
                        st.html(render_component(
                            "News Sentiment Risk", 15, score_sent,
                            f"Based on today's financial news about your holdings. "
                            f"{_sentiment_neg_count} of your {len(current_assets)} stocks have negative news coverage right now. "
                            f"Overall portfolio sentiment is {_sent_label} ({portfolio_sentiment_score:+.2f}).",
                            "score = 50 \u2212 (sentiment_score \u00d7 40)"
                        ))

                    st.markdown("---")
                    st.markdown("### 🛠️ How to lower your score")
                    st.markdown("Based on the mathematical breakdown, taking these actions will most efficiently reduce your composite risk:")

                    scores_dict = {
                        "Concentration": score_conc,
                        "Volatility":    score_vol,
                        "Drawdown":      score_dd,
                        "Correlation":   score_corr,
                        "Momentum":      score_mom,
                        "Sentiment":     score_sent,
                    }
                    sorted_scores = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)

                    for k, v in sorted_scores[:3]:
                        if k == "Concentration":
                            st.info(f"**Reduce Concentration:** Trim **{top_asset['Name']}** from {top_pct:.1f}% to under {100/len(df) * 1.5:.1f}%. This alone would heavily reduce your Concentration sub-score.")
                        elif k == "Volatility":
                            st.info(f"**Lower Volatility:** Shift capital from high-beta equities into lower volatility assets like Digital Gold or Bonds.")
                        elif k == "Drawdown":
                            st.info(f"**Cut Losers:** Sell off your largest unrealised losing position to instantly clear the Drawdown risk penalty.")
                        elif k == "Correlation":
                            st.info(f"**Improve Diversification:** Sell highly correlated assets in identical sectors and add uncorrelated assets (like commodities).")
                        elif k == "Momentum":
                            st.info(f"**Trim Downward Trends:** {mom_count} of your assets are actively dropping in the 1-month window. Don't average down until momentum flips positive.")
                        elif k == "Sentiment":
                            st.info(f"**Monitor News Flow:** {_sentiment_neg_count} of your holdings currently have negative news sentiment. Watch for earnings misses, downgrades, or sector-level headwinds.")

            with _rtab2:
                if not df.empty:
                    # ── Compare & Analyze ────────────────────────────────────────────
                    st.markdown("---")
                    st.markdown("### 🔬 Compare & Analyze")

                    _ct1, _ct2 = st.tabs(["📈 Portfolio vs Market", "🔍 Compare stocks"])

                    with _ct1:
                        try:
                            _pw = float((df["Weight %"] * df["1Y Ret %"]).sum() / 100.0)
                        except Exception:
                            _pw = float('nan')

                        _nret, _sret = _idx_ret("^NSEI"), _idx_ret("^BSESN")
                        _bx = ["Your portfolio", "NIFTY 50", "SENSEX"]
                        _by = [_pw, _nret if _nret is not None else 0.0, _sret if _sret is not None else 0.0]
                        _figc = px.bar(x=_bx, y=_by, text=[f"{v:.1f}%" for v in _by],
                                       labels={"x": "", "y": "1-year return %"})
                        _figc.update_traces(marker_color=[_pal['accent'], _pal['text_3'], _pal['text_3']])
                        _figc.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
                        ui_theme.style_fig(_figc)
                        st.plotly_chart(_figc, use_container_width=True)
                        if _nret is not None and not pd.isna(_pw):
                            _delta = _pw - _nret
                            if _delta >= 0:
                                st.success(f"You're **beating NIFTY by {_delta:.1f}%** over the last year.")
                            else:
                                st.warning(f"You're **trailing NIFTY by {abs(_delta):.1f}%** over the last year.")

                    with _ct2:
                        _names = st.text_input("Enter 2+ companies (comma-separated)",
                                               placeholder="e.g. Reliance, TCS, Infosys", key="cmp_names")
                        _cc1, _cc2 = st.columns(2)
                        _plbl = _cc1.selectbox("Period", ["1D", "1M", "3M", "6M", "1Y", "3Y", "5Y", "Custom"],
                                               index=3, key="cmp_period")
                        _ctype = _cc2.selectbox("Chart type", ["Line", "Area", "Bar", "Candlestick"], key="cmp_ctype")
                        _start = _end = None
                        if _plbl == "Custom":
                            import datetime as _cdt
                            _dc1, _dc2 = st.columns(2)
                            _start = _dc1.date_input("From", value=_cdt.date.today() - _cdt.timedelta(days=180), key="cmp_from")
                            _end = _dc2.date_input("To", value=_cdt.date.today(), key="cmp_to")

                        if st.button("Compare", key="cmp_go") and _names.strip():
                            _resolved = []
                            for _n in [x.strip() for x in _names.split(",") if x.strip()]:
                                _sym = _cmp_lookup(_n)
                                if _sym:
                                    _resolved.append((_n, _sym))
                            if not _resolved:
                                st.warning("Couldn't resolve any tickers from those names.")
                            else:
                                _norm = pd.DataFrame()
                                _rows = []
                                _ohlc_first, _first_sym = None, None
                                for _n, _sym in _resolved:
                                    _h = _cmp_fetch(_sym, _plbl, _start, _end)
                                    if _h is None or _h.empty:
                                        continue
                                    _s = _h["Close"].dropna()
                                    if len(_s) < 2:
                                        continue
                                    if _ohlc_first is None:
                                        _ohlc_first, _first_sym = _h, _sym
                                    _norm[_sym] = _s / _s.iloc[0] * 100
                                    _ret = (_s.iloc[-1] / _s.iloc[0] - 1) * 100
                                    _vol = _s.pct_change().std() * (252 ** 0.5) * 100
                                    try:
                                        _r = _cmp_rsi(_s)
                                    except Exception:
                                        _r = float('nan')
                                    _ind = _cmp_indic(_sym)
                                    _rsi_v = _ind.get("rsi", _r)
                                    if pd.isna(_rsi_v):
                                        _rsi_v = _r
                                    _ma = _s.rolling(min(200, len(_s))).mean().iloc[-1]
                                    _above = _s.iloc[-1] > _ma
                                    if not pd.isna(_rsi_v) and _rsi_v < 35 and _above:
                                        _sig = "🟢 Accumulate"
                                    elif not pd.isna(_rsi_v) and _rsi_v > 70:
                                        _sig = "🔴 Overbought"
                                    elif not _above:
                                        _sig = "🟠 Below 200-DMA"
                                    else:
                                        _sig = "⚪ Neutral"
                                    _rows.append({"Stock": _n, "Return %": round(_ret, 1),
                                                  "Vol %": round(_vol, 1),
                                                  "RSI": round(_rsi_v) if not pd.isna(_rsi_v) else None,
                                                  "50/200": _ind.get("trend", "—"),
                                                  "MACD": _ind.get("macd", "—"),
                                                  "52w %": _ind.get("pos52"),
                                                  "Signal": _sig})

                                if _ctype == "Candlestick" and _ohlc_first is not None:
                                    _figk = go.Figure(go.Candlestick(
                                        x=_ohlc_first.index, open=_ohlc_first["Open"], high=_ohlc_first["High"],
                                        low=_ohlc_first["Low"], close=_ohlc_first["Close"], name=_first_sym))
                                    _cl = _ohlc_first["Close"]
                                    _sma20 = _cl.rolling(20).mean()
                                    _std20 = _cl.rolling(20).std()
                                    _figk.add_scatter(x=_ohlc_first.index, y=_sma20, mode="lines", name="SMA 20",
                                                      line=dict(width=1.2, color=_pal['accent']))
                                    _figk.add_scatter(x=_ohlc_first.index, y=_sma20 + 2 * _std20, mode="lines", name="BB upper",
                                                      line=dict(width=1, color=_pal['text_3'], dash="dot"))
                                    _figk.add_scatter(x=_ohlc_first.index, y=_sma20 - 2 * _std20, mode="lines", name="BB lower",
                                                      line=dict(width=1, color=_pal['text_3'], dash="dot"))
                                    if len(_cl) >= 50:
                                        _figk.add_scatter(x=_ohlc_first.index, y=_cl.rolling(50).mean(), mode="lines",
                                                          name="SMA 50", line=dict(width=1.2, color=_pal['warn']))
                                    _figk.update_layout(height=400, margin=dict(t=30, b=0, l=0, r=0),
                                                        title=f"{_first_sym} · {_plbl}", xaxis_rangeslider_visible=False)
                                    ui_theme.style_fig(_figk)
                                    st.plotly_chart(_figk, use_container_width=True)
                                    if len(_resolved) > 1:
                                        st.caption("Candlestick shows the first stock only — use Line/Area/Bar to compare several.")
                                elif not _norm.empty:
                                    _lbls = {"value": "Growth (rebased to 100)", "index": "", "variable": "Stock"}
                                    if _ctype == "Bar":
                                        _fign = px.bar(_norm, barmode="group", labels=_lbls)
                                    elif _ctype == "Area":
                                        _fign = px.area(_norm, labels=_lbls)
                                    else:
                                        _fign = px.line(_norm, labels=_lbls)
                                    _fign.update_layout(height=360, margin=dict(t=10, b=0, l=0, r=0))
                                    ui_theme.style_fig(_fign)
                                    st.plotly_chart(_fign, use_container_width=True)

                                if _rows:
                                    st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
                                    st.caption(f"{_plbl} window · 50/200, MACD, RSI, 52w computed on 1-year data · heuristic, not advice.")

                                if _first_sym:
                                    _f = _cmp_fund(_first_sym)
                                    if any(v is not None for v in _f.values()):
                                        with st.expander(f"📋 Fundamentals · {_first_sym}"):
                                            _fc = st.columns(4)
                                            _fc[0].metric("P/E", f"{_f['pe']:.1f}" if _f.get('pe') else "—")
                                            _fc[1].metric("Market cap", f"₹{_f['mcap']/1e7:,.0f} Cr" if _f.get('mcap') else "—")
                                            _fc[2].metric("Div yield", f"{_f['dy']*100:.2f}%" if _f.get('dy') else "—")
                                            _fc[3].metric("Beta", f"{_f['beta']:.2f}" if _f.get('beta') is not None else "—")

            st.stop() # Halt execution so the main dashboard doesn't render below the breakdown view

    # Split view for Data and Insights
    # ── Section routing (sidebar nav replaces 9 tabs) ──────────────────────────
    _SEC_OF = {
        "tab1": "Overview",
        "tab2": "Analytics", "tab_math": "Analytics",
        "tab5": "Projections",
        "tab3": "Insights",
        "tab6": "News",
        "tab4": "Activity",
        "tab_chat": "Chat",
        "tab_michael": "MICHAEL",
    }

    def _active(name):
        """True if the tab's section is the one currently selected. Inactive
        sections are skipped entirely — no flash, and only one section's code
        runs per rerun (much faster)."""
        return section == _SEC_OF[name]

