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
    import json as _pj, os as _po, calendar as _pcal, datetime as _pdt
    _ppal = ui_theme.palette()
    _pdir = st.session_state.get("_quest_data_dir", ".")
    _ev_file = _po.path.join(_pdir, "events.json")
    _tk_file = _po.path.join(_pdir, "tasks.json")

    def _pload(path, default):
        try:
            with open(path, encoding="utf-8") as f:
                return _pj.load(f)
        except Exception:
            return default

    def _psave(path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                _pj.dump(data, f, indent=2)
        except Exception:
            pass

    _events = _pload(_ev_file, [])
    _tasks = _pload(_tk_file, [])

    st.markdown(
        f"<div style='font-size:1.4rem;font-weight:500;color:var(--q-text);margin-bottom:2px;'>Planner</div>"
        f"<div style='font-size:.85rem;color:var(--q-text-3);margin-bottom:14px;'>Your events and to-dos — "
        f"the Overview calendar is a read-only glance; edit here.</div>", unsafe_allow_html=True)

    _ptab1, _ptab2 = st.tabs(["📅 Calendar", "✓  To-do"])

    # ── Calendar tab ──────────────────────────────────────────────────────────
    with _ptab1:
        if "plan_offset" not in st.session_state:
            st.session_state.plan_offset = 0
        _ptoday = _pdt.date.today()
        _pbi = _ptoday.year * 12 + (_ptoday.month - 1) + st.session_state.plan_offset
        _pyr, _pmo = divmod(_pbi, 12)
        _pmo += 1

        _pc1, _pc2, _pc3 = st.columns([1, 4, 1])
        if _pc1.button("‹", key="plan_prev", use_container_width=True):
            st.session_state.plan_offset -= 1
            st.rerun()
        if _pc3.button("›", key="plan_next", use_container_width=True):
            st.session_state.plan_offset += 1
            st.rerun()
        _pc2.markdown(
            f"<div style='text-align:center;font-size:1.05rem;font-weight:500;color:var(--q-text);"
            f"font-family:\"JetBrains Mono\",monospace;padding-top:6px;'>"
            f"{_pdt.date(_pyr, _pmo, 1).strftime('%B %Y')}</div>", unsafe_allow_html=True)

        _ev_dates = {}
        for _e in _events:
            _ev_dates.setdefault(_e.get("date", ""), []).append(_e)
        try:
            import nse_live as _nse_p
            _hols = _nse_p.get_holiday_calendar()
        except Exception:
            _hols = {}

        _dow = "".join(
            f"<div style='text-align:center;font-size:.68rem;color:{_ppal['text_3']};"
            f"font-weight:500;text-transform:uppercase;letter-spacing:1px;padding:4px 0;'>{_d}</div>"
            for _d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
        _cells = ""
        for _wk in _pcal.Calendar(firstweekday=0).monthdatescalendar(_pyr, _pmo):
            for _day in _wk:
                _ds = _day.strftime("%Y-%m-%d")
                _in = _day.month == _pmo
                _color = _ppal['text'] if _in else _ppal['border_2']
                _border = "1px solid transparent"
                _extra = ""
                _title = ""
                if _ds in _hols and _in:
                    _border = f"1px solid {_ppal['neg']}"
                    _title = _hols[_ds]
                if _day == _ptoday:
                    _border = f"2px solid {_ppal['accent']}"
                    _extra = "font-weight:500;"
                _dots = ""
                if _in and _ds in _ev_dates:
                    _dots = f"<span style='display:block;width:5px;height:5px;border-radius:50%;background:{_ppal['accent']};margin:2px auto 0;'></span>"
                    _title = "; ".join(e.get("title", "") for e in _ev_dates[_ds])
                elif _in and _ds in _hols:
                    _dots = f"<span style='display:block;width:5px;height:5px;border-radius:50%;background:{_ppal['neg']};margin:2px auto 0;'></span>"
                _cells += (
                    f"<div title='{_title}' style='height:42px;display:flex;flex-direction:column;"
                    f"align-items:center;justify-content:center;border-radius:7px;border:{_border};"
                    f"color:{_color};font-size:.8rem;font-family:\"JetBrains Mono\",monospace;{_extra}'>{_day.day}{_dots}</div>")

        st.markdown(
            f"<div class='q-card q-enter' style='margin-bottom:10px;'>"
            f"<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:4px;'>{_dow}</div>"
            f"<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin-top:6px;'>{_cells}</div>"
            f"<div style='margin-top:12px;padding-top:10px;border-top:1px solid {_ppal['border']};font-size:.72rem;color:{_ppal['text_3']};'>"
            f"<span style='color:{_ppal['accent']};'>●</span> Your event &nbsp;&nbsp;"
            f"<span style='color:{_ppal['neg']};'>●</span> Market holiday</div></div>", unsafe_allow_html=True)

        with st.expander("＋  Add an event"):
            with st.form("plan_add_event"):
                _ed = st.date_input("Date", value=_ptoday, key="ev_date")
                _et = st.text_input("Title", key="ev_title", placeholder="e.g. Review portfolio, RELIANCE results")
                _en = st.text_input("Note (optional)", key="ev_note")
                if st.form_submit_button("Add event"):
                    if _et.strip():
                        _events.append({"date": str(_ed), "title": _et.strip(), "note": _en.strip()})
                        _psave(_ev_file, _events)
                        st.success("Event added")
                        time.sleep(0.4)
                        st.rerun()

        _month_ev = sorted([e for e in _events if e.get("date", "")[:7] == f"{_pyr:04d}-{_pmo:02d}"],
                           key=lambda x: x.get("date", ""))
        if _month_ev:
            st.markdown("**Events this month**")
            for _i, _e in enumerate(_month_ev):
                _ec1, _ec2 = st.columns([8, 1])
                _note = f" — <span style='color:{_ppal['text_3']};'>{_e.get('note','')}</span>" if _e.get("note") else ""
                _ec1.markdown(
                    f"<div style='padding:7px 0;'><span style='font-family:\"JetBrains Mono\",monospace;color:{_ppal['accent']};'>"
                    f"{_e.get('date','')}</span> · <b style='color:var(--q-text);'>{_e.get('title','')}</b>{_note}</div>",
                    unsafe_allow_html=True)
                if _ec2.button("🗑", key=f"del_ev_{_i}_{_e.get('date','')}"):
                    _events.remove(_e)
                    _psave(_ev_file, _events)
                    st.rerun()

    # ── To-do tab ─────────────────────────────────────────────────────────────
    with _ptab2:
        _tc1, _tc2 = st.columns([5, 1])
        _newtask = _tc1.text_input("New task", key="new_task", placeholder="What needs doing?",
                                   label_visibility="collapsed")
        if _tc2.button("Add", key="add_task", use_container_width=True) and _newtask.strip():
            _tasks.append({"text": _newtask.strip(), "done": False})
            _psave(_tk_file, _tasks)
            st.rerun()

        _open_tasks = [t for t in _tasks if not t.get("done")]
        _done_tasks = [t for t in _tasks if t.get("done")]
        _n_open = len(_open_tasks)
        st.markdown(f"<div style='font-size:.8rem;color:var(--q-text-3);margin:8px 0;'>"
                    f"{_n_open} open · {len(_done_tasks)} done</div>", unsafe_allow_html=True)

        for _i, _t in enumerate(_tasks):
            _tk1, _tk2 = st.columns([9, 1])
            _checked = _tk1.checkbox(_t.get("text", ""), value=_t.get("done", False), key=f"task_{_i}")
            if _checked != _t.get("done", False):
                _t["done"] = _checked
                _psave(_tk_file, _tasks)
                st.rerun()
            if _tk2.button("🗑", key=f"del_task_{_i}"):
                _tasks.remove(_t)
                _psave(_tk_file, _tasks)
                st.rerun()

        if not _tasks:
            st.info("No tasks yet — add your first above.")
