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
    st.markdown(
        f"<div style='font-size:1.15rem;font-weight:500;color:var(--q-text);margin-bottom:10px;'>"
        f"Holdings <span style='color:var(--q-text-3);'>· {len(df)}</span></div>",
        unsafe_allow_html=True,
    )

    def _lookup_ticker(name):
        if not name or not name.strip():
            return None
        try:
            import urllib.request, urllib.parse, json as _json
            url = "https://query2.finance.yahoo.com/v1/finance/search?q=" + urllib.parse.quote(name.strip())
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                data = _json.load(r)
            quotes = data.get("quotes", [])
            for suffix in (".NS", ".BO"):
                for q in quotes:
                    if str(q.get("symbol", "")).endswith(suffix):
                        return q["symbol"]
            return quotes[0].get("symbol") if quotes else None
        except Exception:
            return None

    if not df.empty:
        def _risk_tone(b):
            b = str(b).upper()
            return 'pos' if b == 'LOW' else 'warn' if b == 'MODERATE' else 'neg'
        _cards = ""
        for _, r in df.iterrows():
            _pos = r['P&L (₹)'] >= 0
            _cls = 'q-pos' if _pos else 'q-neg'
            _sgn = '+' if _pos else '−'
            _tone = _risk_tone(r['Risk Bucket'])
            _wt = min(float(r['Weight %']), 100.0)
            _barcol = 'var(--q-pos)' if _pos else 'var(--q-text-3)'
            _cards += (
                "<div class='q-card q-enter' style='padding:13px 16px;margin-bottom:8px;'>"
                "<div style='display:flex;justify-content:space-between;align-items:center;'>"
                "<div style='display:flex;align-items:center;gap:10px;'>"
                f"<span style='font-weight:500;color:var(--q-text);'>{r['Name']}</span>"
                f"<span class='q-pill' style='background:var(--q-surface-2);color:var(--q-text-2);'>{str(r['Type']).upper()}</span></div>"
                "<div class='q-mono' style='text-align:right;'>"
                f"<div style='font-weight:500;color:var(--q-text);'>₹{r['Current Value (₹)']:,.2f}</div>"
                f"<div class='{_cls}' style='font-size:.8rem;'>{_sgn}{abs(r['P&L %']):.2f}% · {_sgn}₹{abs(r['P&L (₹)']):,.2f}</div></div></div>"
                "<div style='display:flex;justify-content:space-between;align-items:center;margin-top:7px;font-size:.72rem;color:var(--q-text-3);'>"
                f"<span class='q-mono'>{r['Quantity']:g} units · invested ₹{r['Invested (₹)']:,.2f}</span>"
                f"{ui_theme.pill(str(r['Risk Bucket']).title() + ' risk', _tone)}</div>"
                "<div style='height:5px;background:var(--q-surface-2);border-radius:3px;margin-top:9px;overflow:hidden;'>"
                f"<div class='q-bar' style='width:{_wt:.1f}%;height:100%;background:{_barcol};'></div></div></div>"
            )
        st.markdown(_cards, unsafe_allow_html=True)

    with st.expander("＋  Add a stock", expanded=df.empty):
        _na = st.text_input("Company / fund name", key="ov_add_name", placeholder="e.g. Reliance Industries")
        _cfind, _cnote = st.columns([1, 2])
        with _cfind:
            if st.button("Find ticker", key="ov_find_ticker", use_container_width=True):
                _sym = _lookup_ticker(st.session_state.get("ov_add_name", ""))
                if _sym:
                    st.session_state["ov_add_id"] = _sym
                    st.session_state["_ov_lookup_msg"] = ("ok", _sym)
                else:
                    st.session_state["_ov_lookup_msg"] = ("err", "")
        _msg = st.session_state.get("_ov_lookup_msg")
        if _msg and _msg[0] == "ok":
            _cnote.success(f"Found {_msg[1]} — verify below, then add.")
        elif _msg and _msg[0] == "err":
            _cnote.warning("No match found — enter the ticker manually.")
        _ty = st.selectbox("Type", [AssetType.EQUITY, AssetType.ETF, AssetType.MUTUAL_FUND, AssetType.DIGITAL_GOLD], key="ov_add_type")
        _id = st.text_input("Identifier (ticker / scheme code)", key="ov_add_id", help="Auto-filled from the name — verify before adding.")
        _am = st.number_input("Invested amount (₹)", min_value=0.0, value=0.0, step=100.0, key="ov_add_amt")
        _qt = st.number_input("Quantity (units)", min_value=0.0, value=0.0, step=1.0, key="ov_add_qty")
        if st.button("Add stock", key="ov_add_submit"):
            if _na and add_asset(_na, _ty, _id, _am, _qt):
                st.session_state.pop("_ov_lookup_msg", None)
                st.success(f"Added {_na}")
                time.sleep(0.6)
                st.rerun()
            else:
                st.error("Could not add (already exists or invalid).")

    if not df.empty:
        with st.expander("✎  Edit amounts & quantities"):
            edited_df = st.data_editor(
                df.copy(), use_container_width=True,
                column_config={
                    "Invested (₹)": st.column_config.NumberColumn("Invested (₹)", min_value=0.0, format="₹ %.2f", step=0.01),
                    "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, format="%.4f", step=0.0001),
                    "Current Value (₹)": st.column_config.NumberColumn("Current Value", format="₹ %.2f"),
                    "P&L (₹)": st.column_config.NumberColumn("P&L", format="₹ %.2f"),
                    "P&L %": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
                    "Weight %": st.column_config.ProgressColumn("Weight %", format="%.1f %%", min_value=0, max_value=100),
                    "Risk Score": st.column_config.NumberColumn("Risk Score", format="%.1f"),
                    "Risk Bucket": st.column_config.TextColumn("Risk"),
                },
                disabled=["Risk Rank", "Name", "Type", "Last Price", "Current Value (₹)", "P&L (₹)", "P&L %", "Volatility %", "Beta", "Max DD %", "Sharpe", "1d VaR %", "1M Ret %", "6M Ret %", "1Y Ret %", "Total Return %", "Ann Return %", "Profit Factor", "Win Rate %", "RSI", "52w Pos", "Dist 200DMA %", "Risk Score", "Risk Bucket", "Weight %"],
                hide_index=True, key="portfolio_editor",
            )
            changes_made = False
            for idx2, row in edited_df.iterrows():
                if df.loc[idx2, "Invested (₹)"] != row["Invested (₹)"] or df.loc[idx2, "Quantity"] != row["Quantity"]:
                    update_asset_holdings(row["Name"], float(row["Invested (₹)"]), float(row["Quantity"]))
                    changes_made = True
            if changes_made:
                st.success("Saved!")
                time.sleep(0.5)
                st.rerun()

        with st.expander("🗑  Remove a stock"):
            with st.form("ov_remove_form"):
                _rm = st.selectbox("Select stock to remove", list(df["Name"]))
                if st.form_submit_button("Remove"):
                    if remove_asset(_rm):
                        st.success(f"Removed {_rm}")
                        time.sleep(0.6)
                        st.rerun()
    else:
        st.caption("Add your first stock above to bring your dashboard to life.")

