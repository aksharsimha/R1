import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
import plotly.express as px
import plotly.graph_objects as go
import time
import uuid as _uuid
import re as _re
import smtplib as _smtplib
from email.mime.text import MIMEText as _MIMEText
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
    _today = _pdt.date.today()
    _now = _pdt.datetime.now()

    def _normalise_task(task):
        status = task.get("status")
        if status not in {"Pending", "Completed", "Failed"}:
            status = "Completed" if task.get("done", False) else "Pending"
        due_date = task.get("due_date", "")
        if due_date and not isinstance(due_date, str):
            due_date = str(due_date)
        return {
            "id": task.get("id") or _uuid.uuid4().hex,
            "title": task.get("title", task.get("text", "")).strip(),
            "description": task.get("description", task.get("notes", "")),
            "priority": task.get("priority", "Medium") if task.get("priority", "Medium") in {"High", "Medium", "Low"} else "Medium",
            "due_date": due_date,
            "due_time": task.get("due_time", ""),
            "category": task.get("category", "General") or "General",
            "reminder": task.get("reminder", ""),
            "estimate": task.get("estimate", ""),
            "subtasks": task.get("subtasks", []),
            "recurrence": task.get("recurrence", "Does not repeat"),
            "reminder_sent": task.get("reminder_sent", ""),
            "status": status,
        }

    _tasks = [_normalise_task(t) for t in _tasks if isinstance(t, dict) and (t.get("title") or t.get("text"))]

    def _reminder_time(task):
        if not task.get("reminder") or not task.get("due_date"):
            return None
        try:
            due = _pdt.datetime.fromisoformat(f"{task['due_date']}T{(task.get('due_time') or '09:00')[:5]}")
        except (TypeError, ValueError):
            return None
        reminder = task["reminder"].strip().lower()
        if reminder in {"at due time", "at due", "on time", "now"}:
            return due
        if reminder.isdigit():
            return due - _dt.timedelta(minutes=int(reminder))
        match = _re.search(r"(\d+)\s*(minute|minutes|min|hour|hours|day|days)", reminder)
        if not match:
            return None
        amount = int(match.group(1))
        unit = match.group(2)
        delta = _dt.timedelta(minutes=amount) if unit.startswith("min") else _dt.timedelta(hours=amount) if unit.startswith("hour") else _dt.timedelta(days=amount)
        return due - delta if "before" in reminder or "prior" in reminder or "ahead" in reminder else due

    def _send_task_reminder(task, recipient):
        import ssl
        sender = ""
        password = ""
        try:
            sender = str(st.secrets.get("SMTP_EMAIL", "")).strip()
            password = str(st.secrets.get("SMTP_PASSWORD", "")).replace(" ", "").strip()
        except Exception:
            pass

        if not sender or not password:
            import os
            import toml
            here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            secrets_file = os.path.join(here, ".streamlit", "secrets.toml")
            if os.path.exists(secrets_file):
                try:
                    data = toml.load(secrets_file)
                    sender = sender or str(data.get("SMTP_EMAIL", "")).strip()
                    password = password or str(data.get("SMTP_PASSWORD", "")).replace(" ", "").strip()
                except Exception:
                    pass

        if not sender or not password or not recipient:
            return False
        message = _MIMEText(
            f"Reminder from QUEST\n\n{task['title']}\n\n"
            f"Due: {task.get('due_date', 'No date')} {task.get('due_time', '')}\n"
            f"Category: {task.get('category', 'General')}\n\n"
            f"{task.get('description', '')}".strip(), "plain")
        message["From"] = f"QUEST Planner <{sender}>"
        message["To"] = recipient
        message["Subject"] = f"QUEST reminder: {task['title']}"
        server = None
        try:
            try:
                server = _smtplib.SMTP("smtp.gmail.com", 587, local_hostname="localhost", timeout=20)
                server.starttls()
                server.login(sender, password)
                server.send_message(message)
                return True
            except Exception as e587:
                context = ssl.create_default_context()
                with _smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, local_hostname="localhost", timeout=20) as ssl_server:
                    ssl_server.login(sender, password)
                    ssl_server.send_message(message)
                    return True
        except Exception as error:
            print(f"Failed to send task reminder to {recipient}: {error}")
            return False
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass

    def _dispatch_task_reminders(tasks):
        recipient = str((_user_info or {}).get("email", "")).strip()
        if not recipient:
            return False
        changed = False
        current_time = _pdt.datetime.now()
        for task in tasks:
            target = _reminder_time(task)
            if task["status"] != "Pending" or target is None or task.get("reminder_sent"):
                continue
            if current_time >= target:
                if _send_task_reminder(task, recipient):
                    task["reminder_sent"] = current_time.isoformat(timespec="seconds")
                    changed = True
        return changed

    if _dispatch_task_reminders(_tasks):
        _psave(_tk_file, _tasks)

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
        _status_colors = {"Completed": _ppal["pos"], "Failed": _ppal["neg"], "Pending": _ppal["warn"]}
        _priority_colors = {"High": _ppal["neg"], "Medium": _ppal["warn"], "Low": _ppal["pos"]}
        _counts = {s: sum(t["status"] == s for t in _tasks) for s in ("Completed", "Failed", "Pending")}
        _rate = round(_counts["Completed"] / len(_tasks) * 100) if _tasks else 0
        st.markdown(
            f"<div class='q-card q-enter' style='padding:14px 16px;margin-bottom:12px;'>"
            f"<div style='font-size:.76rem;color:var(--q-text-3);text-transform:uppercase;letter-spacing:1px;'>Productivity</div>"
            f"<div style='display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 10px;font-size:.86rem;'>"
            f"<span><b>{len(_tasks)}</b> Total</span><span style='color:{_ppal['pos']}'><b>{_counts['Completed']}</b> Completed</span>"
            f"<span style='color:{_ppal['neg']}'><b>{_counts['Failed']}</b> Failed</span><span style='color:{_ppal['warn']}'><b>{_counts['Pending']}</b> Pending</span>"
            f"<span style='margin-left:auto;color:var(--q-accent);'><b>{_rate}%</b> Completion Rate</span></div>"
            f"<div style='height:7px;background:var(--q-surface-2);border-radius:5px;overflow:hidden;'>"
            f"<div style='height:100%;width:{_rate}%;background:var(--q-accent);transition:width .35s ease;'></div></div></div>", unsafe_allow_html=True)

        with st.expander("＋  Add task", expanded=not _tasks):
            with st.form("add_productivity_task", clear_on_submit=True):
                _a1, _a2 = st.columns([2, 1])
                _title = _a1.text_input("Task title", placeholder="What needs doing?")
                _priority = _a2.selectbox("Priority", ["High", "Medium", "Low"], index=1)
                _description = st.text_area("Description / notes", height=70)
                _a3, _a4, _a5 = st.columns(3)
                _due = _a3.date_input("Due date", value=None)
                _due_time = _a4.time_input("Due time", value=None)
                _category = _a5.text_input("Category", value="General")
                _a6, _a7, _a8 = st.columns(3)
                _reminder = _a6.text_input("Reminder", placeholder="e.g. 30 min before")
                _estimate = _a7.text_input("Estimated time", placeholder="e.g. 45 min")
                _repeat = _a8.selectbox("Repeat", ["Does not repeat", "Daily", "Every weekday", "Weekly", "Monthly", "Custom"])
                _subtasks_text = st.text_area("Subtasks / checklist", placeholder="One item per line", height=60)
                if st.form_submit_button("Create task", type="primary"):
                    if _title.strip():
                        _tasks.append({"id": _uuid.uuid4().hex, "title": _title.strip(), "description": _description.strip(),
                                       "priority": _priority, "due_date": str(_due) if _due else "", "due_time": str(_due_time) if _due_time else "",
                                       "category": _category.strip() or "General", "reminder": _reminder.strip(), "estimate": _estimate.strip(),
                                       "subtasks": [{"text": x.strip(), "done": False} for x in _subtasks_text.splitlines() if x.strip()],
                                       "recurrence": _repeat, "status": "Pending"})
                        _psave(_tk_file, _tasks)
                        st.rerun()

        _test_col, _test_info = st.columns([1, 3])
        if _test_col.button("Send test email", key="send_task_test_email"):
            _recipient = str((_user_info or {}).get("email", "")).strip()
            _test_task = {"title": "QUEST email test", "due_date": str(_today), "due_time": "now",
                          "category": "Planner", "description": "Your QUEST Gmail reminder setup is working."}
            if not _recipient:
                st.error("No linked email is available for this account.")
            elif _send_task_reminder(_test_task, _recipient):
                st.success(f"Test email sent to {_recipient}.")
            else:
                st.error("Email could not be sent. Check the Gmail App Password and SMTP settings.")

        _f1, _f2, _f3, _f4 = st.columns([2, 1, 1, 1])
        _search = _f1.text_input("Search tasks", placeholder="Search title, notes, category", label_visibility="collapsed")
        _view = _f2.selectbox("View", ["All Tasks", "Today", "Upcoming", "Overdue", "Completed", "Failed", "High Priority"], label_visibility="collapsed")
        _filter_status = _f3.selectbox("Status", ["Any status", "Pending", "Completed", "Failed"], label_visibility="collapsed")
        _sort = _f4.selectbox("Sort", ["Due date", "Priority", "Category", "Newest"], label_visibility="collapsed")

        def _due_key(task):
            return task.get("due_date") or "9999-12-31"
        def _matches(task):
            due = task.get("due_date", "")
            haystack = " ".join(str(task.get(k, "")) for k in ("title", "description", "category")).lower()
            if _search.strip().lower() not in haystack:
                return False
            if _filter_status != "Any status" and task["status"] != _filter_status:
                return False
            if _view == "Today" and due != str(_today): return False
            if _view == "Upcoming" and (not due or due <= str(_today)): return False
            if _view == "Overdue" and (not due or due >= str(_today) or task["status"] != "Pending"): return False
            if _view == "Completed" and task["status"] != "Completed": return False
            if _view == "Failed" and task["status"] != "Failed": return False
            if _view == "High Priority" and task["priority"] != "High": return False
            return True
        _visible = [t for t in _tasks if _matches(t)]
        if _sort == "Priority":
            _visible.sort(key=lambda t: {"High": 0, "Medium": 1, "Low": 2}[t["priority"]])
        elif _sort == "Category": _visible.sort(key=lambda t: t.get("category", "").lower())
        elif _sort == "Newest": _visible = list(reversed(_visible))
        else: _visible.sort(key=_due_key)
        st.markdown(f"<div style='font-size:.78rem;color:var(--q-text-3);margin:12px 0 8px;'>{len(_visible)} task(s) shown</div>", unsafe_allow_html=True)

        @st.dialog("Task details")
        def _task_dialog(task):
            with st.form(f"edit_task_{task['id']}"):
                _etitle = st.text_input("Task title", value=task["title"])
                _edesc = st.text_area("Description / notes", value=task["description"], height=90)
                _ep, _es = st.columns(2)
                _epriority = _ep.selectbox("Priority", ["High", "Medium", "Low"], index=["High", "Medium", "Low"].index(task["priority"]))
                _estatus = _es.selectbox("Status", ["Pending", "Completed", "Failed"], index=["Pending", "Completed", "Failed"].index(task["status"]))
                _edate = st.date_input("Due date", value=_pdt.date.fromisoformat(task["due_date"]) if task["due_date"] else None)
                _etime = st.text_input("Due time", value=task["due_time"])
                _ecat = st.text_input("Category", value=task["category"])
                _erem = st.text_input("Reminder", value=task["reminder"])
                _eest = st.text_input("Estimated time", value=task["estimate"])
                _erepeat = st.selectbox("Repeat", ["Does not repeat", "Daily", "Every weekday", "Weekly", "Monthly", "Custom"], index=["Does not repeat", "Daily", "Every weekday", "Weekly", "Monthly", "Custom"].index(task["recurrence"]) if task["recurrence"] in ["Does not repeat", "Daily", "Every weekday", "Weekly", "Monthly", "Custom"] else 0)
                _est = st.text_area("Subtasks / checklist", value="\n".join(x.get("text", "") for x in task["subtasks"]), height=70)
                if st.form_submit_button("Save changes", type="primary"):
                    task.update(title=_etitle.strip(), description=_edesc.strip(), priority=_epriority, status=_estatus,
                                due_date=str(_edate) if _edate else "", due_time=_etime.strip(), category=_ecat.strip() or "General",
                                reminder=_erem.strip(), estimate=_eest.strip(), recurrence=_erepeat,
                                subtasks=[{"text": x.strip(), "done": False} for x in _est.splitlines() if x.strip()])
                    _psave(_tk_file, _tasks)
                    st.rerun()

        for _i, _task in enumerate(_visible):
            _due_label = f"Due {_task['due_date']}" if _task["due_date"] else "No due date"
            if _task["due_time"]: _due_label += f" · {_task['due_time'][:5]}"
            _overdue = _task["status"] == "Pending" and _task["due_date"] and _task["due_date"] < str(_today)
            _sub_done = sum(x.get("done", False) for x in _task["subtasks"])
            _desc = (_task["description"][:110] + "…") if len(_task["description"]) > 110 else _task["description"]
            st.markdown(f"<div class='q-card q-enter' style='padding:12px 14px;margin-bottom:8px;border-left:3px solid {_priority_colors[_task['priority']]};opacity:{'0.62' if _task['status'] != 'Pending' else '1'};'>"
                        f"<div style='display:flex;justify-content:space-between;gap:8px;'><b style='color:var(--q-text);'>{_task['title']}</b>"
                        f"<span style='color:{_priority_colors[_task['priority']]};font-size:.74rem;'>● {_task['priority']}</span></div>"
                        f"<div style='font-size:.75rem;color:var(--q-text-3);margin-top:4px;'>{_due_label} · {_task['category']}" + (f" · {_sub_done}/{len(_task['subtasks'])} subtasks" if _task["subtasks"] else "") + (f" · <span style='color:{_ppal['neg']}'>Overdue</span>" if _overdue else "") + "</div>"
                        + (f"<div style='font-size:.79rem;color:var(--q-text-2);margin-top:6px;'>{_desc}</div>" if _desc else "") + "</div>", unsafe_allow_html=True)
            _status_choice = st.selectbox("Status", ["Pending", "Completed", "Failed"],
                                          index=["Pending", "Completed", "Failed"].index(_task["status"]),
                                          key=f"task_status_{_task['id']}", label_visibility="collapsed")
            if _status_choice != _task["status"]:
                _task["status"] = _status_choice
                _psave(_tk_file, _tasks)
                st.rerun()
            _b1, _b2, _b3, _b4, _b5 = st.columns([1, 1.5, 1, 1, 1])
            if _b1.button("Edit", key=f"edit_{_task['id']}"): _task_dialog(_task)
            if _b2.button("Duplicate", key=f"dup_{_task['id']}"):
                _copy = dict(_task); _copy["id"] = _uuid.uuid4().hex; _copy["title"] += " (copy)"; _tasks.insert(_tasks.index(_task) + 1, _copy); _psave(_tk_file, _tasks); st.rerun()
            if _b3.button("Delete", key=f"delete_{_task['id']}"):
                st.session_state[f"confirm_delete_{_task['id']}"] = True
            _task_index = _tasks.index(_task)
            if _b4.button("↑", key=f"up_{_task['id']}", help="Move task up") and _task_index > 0:
                _tasks[_task_index - 1], _tasks[_task_index] = _tasks[_task_index], _tasks[_task_index - 1]
                _psave(_tk_file, _tasks); st.rerun()
            if _b5.button("↓", key=f"down_{_task['id']}", help="Move task down") and _task_index < len(_tasks) - 1:
                _tasks[_task_index + 1], _tasks[_task_index] = _tasks[_task_index], _tasks[_task_index + 1]
                _psave(_tk_file, _tasks); st.rerun()
            if _task["subtasks"]:
                for _sub_i, _subtask in enumerate(_task["subtasks"]):
                    _sub_done = st.checkbox(_subtask.get("text", ""), value=_subtask.get("done", False), key=f"subtask_{_task['id']}_{_sub_i}")
                    if _sub_done != _subtask.get("done", False):
                        _subtask["done"] = _sub_done; _psave(_tk_file, _tasks); st.rerun()
            if st.session_state.get(f"confirm_delete_{_task['id']}"):
                st.warning("Delete this task permanently?")
                _y, _n = st.columns(2)
                if _y.button("Confirm delete", key=f"yes_{_task['id']}"):
                    _tasks.remove(_task); _psave(_tk_file, _tasks); st.session_state.pop(f"confirm_delete_{_task['id']}", None); st.rerun()
                if _n.button("Cancel", key=f"no_{_task['id']}"):
                    st.session_state.pop(f"confirm_delete_{_task['id']}", None); st.rerun()
        if not _visible:
            st.info("No matching tasks. Add a task or adjust your filters.")
