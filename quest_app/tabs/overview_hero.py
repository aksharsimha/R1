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


def render(df=None, summary=None, current_assets=None, _user_info=None,
           portfolio_sentiment_score=None, _sentiment_neg_count=None, comp_score=None):
    total_invested = df['Invested (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl = df['P&L (\u20b9)'].sum() if df is not None and not df.empty else 0.0
    total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    try:
        total_val = summary['total_value']
    except Exception:
        total_val = 0.0
    if df.empty:
        st.markdown(
            "<div class='q-card q-enter' style='margin-bottom:16px;border-left:3px solid var(--q-accent);border-radius:0 12px 12px 0;'>"
            "<div style='font-size:1.1rem;font-weight:500;color:var(--q-text);margin-bottom:4px;'>👋 Welcome to QUEST!</div>"
            "<div style='font-size:.9rem;color:var(--q-text-2);line-height:1.6;'>Your portfolio is empty. "
            "Scroll down to <b>＋ Add a stock</b> (type a company name and we'll find the ticker for you) — "
            "then your live value, risk score, news, and forecast all come to life.</div></div>",
            unsafe_allow_html=True)

    # ── Hero / Overview header (themed) ──────────────────────────────────────
    _pnl_pos = total_pnl >= 0
    _pnl_cls = 'q-pos' if _pnl_pos else 'q-neg'
    _pnl_sign = '+' if _pnl_pos else ''
    _score = summary.get('portfolio_risk_score', 0.0)
    _risk_bucket = summary.get('portfolio_risk_bucket', 'LOW')
    _risk_tone = 'pos' if _score <= 40 else 'warn' if _score <= 70 else 'neg'

    _mkt_status = summary.get('market_status', 'Unknown')
    _mkt_open = summary.get('market_open', False)
    _dominant_src = summary.get('dominant_source', 'historical')
    _mkt_tone = 'pos' if _mkt_open else 'neg'

    _src_map = {
        'nse_live':   ('Live · NSE real-time', 'pos'),
        'yfinance':   ('yfinance · ~15min delay', 'warn'),
        'cached':     ('Last-known price (cached)', 'accent'),
        'historical': ('Historical close', 'accent'),
    }
    _src_label, _src_tone = _src_map.get(_dominant_src, ('Historical close', 'accent'))

    # ── Animated hero: portfolio value + NIFTY/SENSEX benchmarks (count-up) ──
    _hp = ui_theme.palette()
    def _pill_cols(tone):
        return {
            'pos': (_hp['pos_weak'], _hp['pos']),
            'neg': (_hp['neg_weak'], _hp['neg']),
            'warn': (_hp['warn_weak'], _hp['warn']),
            'accent': (_hp['accent_weak'], _hp['accent']),
        }.get(tone, (_hp['accent_weak'], _hp['accent']))
    _mkt_bg, _mkt_fg = _pill_cols(_mkt_tone)
    _src_bg, _src_fg = _pill_cols(_src_tone)
    _pnl_color = _hp['pos'] if _pnl_pos else _hp['neg']
    _prev_val = float(st.session_state.get('_hero_prev_val', 0.0))
    _cur_val = float(summary['total_value'])
    st.session_state['_hero_prev_val'] = _cur_val

    @st.cache_data(ttl=300, show_spinner=False)
    def _fetch_index_quotes():
        out = {}
        try:
            import yfinance as yf
            for _k, _tk in (('NIFTY 50', '^NSEI'), ('SENSEX', '^BSESN')):
                try:
                    _fi = yf.Ticker(_tk).fast_info
                    _last = float(_fi.last_price)
                    _prev = float(_fi.previous_close)
                    out[_k] = {'last': _last, 'chg': ((_last - _prev) / _prev * 100) if _prev else 0.0}
                except Exception:
                    pass
        except Exception:
            pass
        return out
    _idx = _fetch_index_quotes()

    def _idx_card(label, data):
        if not data:
            return ''
        _c = _hp['pos'] if data['chg'] >= 0 else _hp['neg']
        _ar = '▲' if data['chg'] >= 0 else '▼'
        return (
            f"<div style='background:{_hp['surface_2']};border-radius:12px;padding:11px 14px;'>"
            f"<div style='font-size:.68rem;color:{_hp['text_3']};text-transform:uppercase;letter-spacing:.6px;'>{label}</div>"
            f"<div class='cu mono' data-start='0' data-target='{data['last']}' data-dec='2' "
            f"style='font-size:1.2rem;font-weight:500;color:{_hp['text']};margin-top:2px;'>{data['last']:,.2f}</div>"
            f"<div class='mono' style='font-size:.76rem;color:{_c};'>{_ar} {abs(data['chg']):.2f}%</div></div>"
        )
    _idx_html = _idx_card('NIFTY 50', _idx.get('NIFTY 50')) + _idx_card('SENSEX', _idx.get('SENSEX'))
    _idx_col = (f"<div style='flex:1;min-width:160px;display:flex;flex-direction:column;gap:10px;'>{_idx_html}</div>"
                if _idx_html else "")

    _hero_comp = f'''<!doctype html><html><head><meta charset="utf-8">
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');
    *{{margin:0;box-sizing:border-box;}} html,body{{background:transparent;}}
    body{{font-family:Inter,sans-serif;}}
    .mono{{font-family:"JetBrains Mono",monospace;}}
    .pill{{display:inline-flex;align-items:center;font-size:.72rem;padding:3px 10px;border-radius:999px;}}
    @keyframes fin{{from{{opacity:0;transform:translateY(8px);}}to{{opacity:1;transform:translateY(0);}}}}
    .fin{{animation:fin .5s cubic-bezier(.22,.61,.36,1) both;}}
    </style></head><body>
    <div class="fin" style="display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start;">
      <div style="flex:2;min-width:240px;">
        <div style="font-size:.78rem;color:{_hp['text_3']};">Portfolio value</div>
        <div id="qv" class="cu mono" data-start="{_prev_val}" data-target="{_cur_val}" data-dec="2" data-prefix="₹" style="font-size:2.4rem;font-weight:500;color:{_hp['text']};letter-spacing:-1.2px;line-height:1.1;">₹{_cur_val:,.2f}</div>
        <div class="mono" style="font-size:1rem;font-weight:500;margin-top:2px;color:{_pnl_color};">{_pnl_sign}{total_pnl_perc:.2f}% · {_pnl_sign}₹{total_pnl:,.2f}</div>
        <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
          <span class="pill" style="background:{_mkt_bg};color:{_mkt_fg};">{_mkt_status}</span>
          <span class="pill" style="background:{_src_bg};color:{_src_fg};">{_src_label}</span>
        </div>
      </div>
      {_idx_col}
    </div>
    <script>
    (function(){{
      var rm=window.matchMedia('(prefers-reduced-motion:reduce)').matches;
      function fmt(n,dec,prefix){{return (prefix||'')+Number(n).toLocaleString('en-IN',{{minimumFractionDigits:dec,maximumFractionDigits:dec}});}}
      document.querySelectorAll('.cu').forEach(function(el){{
        var start=parseFloat(el.getAttribute('data-start'))||0;
        var target=parseFloat(el.getAttribute('data-target'))||0;
        var dec=parseInt(el.getAttribute('data-dec')||'2');
        var prefix=el.getAttribute('data-prefix')||'';
        if(rm||Math.abs(target-start)<0.01){{el.textContent=fmt(target,dec,prefix);return;}}
        var t0=null,d=1100;
        requestAnimationFrame(function s(ts){{if(!t0)t0=ts;var p=Math.min((ts-t0)/d,1);var e=1-Math.pow(1-p,3);el.textContent=fmt(start+(target-start)*e,dec,prefix);if(p<1)requestAnimationFrame(s);}});
      }});
    }})();
    </script></body></html>'''
    st.html(_hero_comp, unsafe_allow_javascript=True)

    st.markdown(f'''
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:4px 0 22px;">
      <div class="q-metric q-enter" style="animation-delay:.05s;"><div class="lbl">Invested</div><div class="val">₹{total_invested:,.2f}</div></div>
      <div class="q-metric q-enter" style="animation-delay:.10s;"><div class="lbl">Assets</div><div class="val">{summary['n_assets']}</div></div>
      <div class="q-metric q-enter" style="animation-delay:.15s;"><div class="lbl">Risk score</div><div class="val" style="color:var(--q-{_risk_tone});">{_score:.1f} · {_risk_bucket.title()}</div></div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Market Holiday Calendar (Google-Calendar style) ──────────────────────
    import calendar as _calmod
    import datetime as _dt
    import nse_live as _nse

    @st.cache_data(ttl=604800, show_spinner=False)  # refresh weekly
    def _load_market_holidays():
        try:
            _nse.refresh_holiday_calendar()
        except Exception:
            pass
        return _nse.get_holiday_calendar()

    _holidays_map = _load_market_holidays()
    _today = _dt.date.today()
    _pal = ui_theme.palette()

    # Load the user's Planner events so the Overview calendar reflects them too
    import json as _ovj, os as _ovo
    try:
        with open(_ovo.path.join(st.session_state.get("_quest_data_dir", "."), "events.json"), encoding="utf-8") as _ovf:
            _ov_events_raw = _ovj.load(_ovf)
    except Exception:
        _ov_events_raw = []
    _ov_evset = {}
    for _ove in _ov_events_raw:
        _ov_evset.setdefault(_ove.get("date", ""), []).append(_ove.get("title", ""))

    if 'cal_offset' not in st.session_state:
        st.session_state.cal_offset = 0

    # Resolve the displayed month from today + offset
    _base_idx = _today.year * 12 + (_today.month - 1) + st.session_state.cal_offset
    _disp_year, _disp_month = divmod(_base_idx, 12)
    _disp_month += 1

    _cprev, _ctitle, _cnext = st.columns([1, 4, 1])
    with _cprev:
        if st.button('‹', key='cal_prev', use_container_width=True):
            st.session_state.cal_offset -= 1
            st.rerun()
    with _cnext:
        if st.button('›', key='cal_next', use_container_width=True):
            st.session_state.cal_offset += 1
            st.rerun()
    with _ctitle:
        _hdr = _dt.date(_disp_year, _disp_month, 1).strftime('%B %Y')
        st.markdown(
            f"<div style='text-align:center;font-size:1.05rem;font-weight:500;"
            f"color:{_pal['text']};font-family:\"JetBrains Mono\",monospace;padding-top:6px;'>"
            f"{_hdr}</div>", unsafe_allow_html=True)

    # Build the month grid (weeks of datetime.date, Monday-first)
    _weeks = _calmod.Calendar(firstweekday=0).monthdatescalendar(_disp_year, _disp_month)
    _dow = "".join(
        f"<div style='text-align:center;font-size:0.68rem;color:{_pal['text_3']};"
        f"font-weight:500;text-transform:uppercase;letter-spacing:1px;padding:4px 0;'>{d}</div>"
        for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    )
    _cells = ""
    for _wk in _weeks:
        for _day in _wk:
            _ds = _day.strftime('%Y-%m-%d')
            _in_month = (_day.month == _disp_month)
            _is_today = (_day == _today)
            _is_weekend = (_day.weekday() >= 5)
            _hol_desc = _holidays_map.get(_ds)
            # base styling (theme-aware)
            _bg = "transparent"
            _color = _pal['text'] if _in_month else _pal['border_2']
            _border = "1px solid transparent"
            _extra = ""
            _title = ""
            if not _in_month:
                _color = _pal['border_2']
            elif _hol_desc:
                _bg = _pal['neg_weak']
                _color = _pal['neg']
                _border = f"1px solid {_pal['neg']}"
                _title = _hol_desc
            elif _is_weekend:
                _color = _pal['text_3']
            if _is_today:
                _border = f"2px solid {_pal['accent']}"
                _extra = "font-weight:500;"
            _has_ev = _in_month and _ds in _ov_evset
            if _has_ev:
                _dot = (f"<span style='display:block;width:5px;height:5px;border-radius:50%;"
                        f"background:{_pal['accent']};margin:2px auto 0;'></span>")
                _title = "; ".join(t for t in _ov_evset[_ds] if t) or _title
            elif _in_month and _hol_desc:
                _dot = (f"<span style='display:block;width:5px;height:5px;border-radius:50%;"
                        f"background:{_pal['neg']};margin:2px auto 0;'></span>")
            else:
                _dot = ""
            _cells += (
                f"<div title='{_title}' style='height:36px;display:flex;flex-direction:column;"
                f"align-items:center;justify-content:center;border-radius:7px;background:{_bg};"
                f"border:{_border};color:{_color};font-size:0.76rem;"
                f"font-family:\"JetBrains Mono\",monospace;{_extra}'>{_day.day}{_dot}</div>"
            )

    # Next upcoming holiday note
    _upcoming = sorted(d for d in _holidays_map if d >= _today.strftime('%Y-%m-%d'))
    if _upcoming:
        _nh = _upcoming[0]
        _nh_date = _dt.datetime.strptime(_nh, '%Y-%m-%d').date()
        _days_to = (_nh_date - _today).days
        _when = "today" if _days_to == 0 else ("tomorrow" if _days_to == 1 else f"in {_days_to} days")
        _next_note = (f"<span style='color:{_pal['neg']};'>●</span> Next holiday: "
                      f"<b style='color:{_pal['text']};'>{_holidays_map[_nh]}</b> "
                      f"<span style='color:{_pal['text_3']};'>· {_nh_date.strftime('%d %b')} ({_when})</span>")
    else:
        _next_note = f"<span style='color:{_pal['text_3']};'>No upcoming holidays on record.</span>"

    st.markdown(f"""
    <div class="q-card q-enter" style="margin-bottom:8px;">
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;">{_dow}</div>
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin-top:6px;">{_cells}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;
           gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid {_pal['border']};
           font-size:0.72rem;">
        <div style="display:flex;gap:14px;color:{_pal['text_3']};">
          <span><span style="color:{_pal['accent']};">▢</span> Today</span>
          <span><span style="color:{_pal['accent']};">●</span> Event</span>
          <span><span style="color:{_pal['neg']};">●</span> Holiday</span>
          <span><span style="color:{_pal['text_3']};">▪</span> Weekend</span>
        </div>
        <div>{_next_note}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _risk_clicked = st.button('View Risk Breakdown ↗', key='risk_trigger_btn')
    if _risk_clicked:
        st.session_state.show_risk_breakdown = True
        st.rerun()

    st.markdown("---")

