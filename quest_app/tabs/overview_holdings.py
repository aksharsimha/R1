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

    def _search_tickers(query: str):
        if not query or not query.strip(): return []
        try:
            import urllib.request, urllib.parse, json as _json
            url = "https://query2.finance.yahoo.com/v1/finance/search?q=" + urllib.parse.quote(query.strip())
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                data = _json.load(r)
            return data.get("quotes", [])
        except Exception:
            return []

    with st.expander("＋  Add a stock", expanded=df.empty):
        _query = st.text_input("🔍 Search for a company or fund", key="ov_search_q", placeholder="e.g. Tata Motors, Zomato, Reliance...")
        
        _na = ""
        _id = ""
        
        if _query.strip():
            _results = _search_tickers(_query)
            if _results:
                # Filter out pure garbage, keep equities and mutual funds from Indian exchanges
                _temp = [q for q in _results if q.get('quoteType') in ('EQUITY', 'MUTUALFUND', 'ETF') and q.get('symbol') and q.get('exchange') in ('NSI', 'BSE')]
                
                # Yahoo Finance BSE (.BO) data is notoriously corrupted/truncated compared to NSE (.NS)
                # We will drop the BSE version if an NSE version is available in the search results
                _nsi_bases = {q['symbol'].replace('.NS', '') for q in _temp if q.get('exchange') == 'NSI'}
                _valid = []
                for q in _temp:
                    if q.get('exchange') == 'BSE':
                        if q['symbol'].replace('.BO', '') in _nsi_bases:
                            continue # Skip BSE if NSE exists
                    _valid.append(q)
                if _valid:
                    _opts = [f"{q.get('longname', q.get('shortname', 'Unknown'))} ({q['symbol']}) — {q.get('exchDisp', 'Unknown')}" for q in _valid]
                    # Add a manual override option
                    _opts.append("— Enter ticker manually —")
                    
                    _choice = st.selectbox("Select Asset", _opts, key="ov_search_sel")
                    
                    if _choice != "— Enter ticker manually —":
                        # Extract symbol inside parenthesis
                        import re
                        _match = re.search(r'\((.*?)\)', _choice)
                        if _match:
                            _id = _match.group(1)
                            _na = _choice.split(" (")[0]
                else:
                    st.warning("No valid stocks found. Enter details manually.")
            else:
                st.warning("No matches found. Enter details manually.")
                
        # If they haven't searched, or chose manual, or search failed, show manual fields
        if not _query.strip() or (locals().get('_choice') == "— Enter ticker manually —") or (not locals().get('_valid') and _query.strip()):
            _na = st.text_input("Company / fund name", value=_na, key="ov_man_name")
            _id = st.text_input("Identifier (ticker / scheme code)", value=_id, key="ov_man_id")

        _ty = st.selectbox("Type", [AssetType.EQUITY, AssetType.ETF, AssetType.MUTUAL_FUND, AssetType.DIGITAL_GOLD], key="ov_add_type")
        _avg_price = st.number_input("Average Buy Price (₹)", min_value=0.01, value=100.0, step=1.0, key="ov_add_price", format="%.2f")
        _qt = st.number_input("Quantity (units)", min_value=0.0001, value=1.0, step=1.0, key="ov_add_qty", format="%.4f")
        
        if st.button("Add stock", key="ov_add_submit"):
            if _na and _id:
                try:
                    # Mathematically calculate the true invested amount based on what they bought it for
                    _am = _avg_price * _qt
                    if add_asset(_na, _ty, _id, _am, _qt):
                        st.success(f"Added {_na}")
                        time.sleep(0.6)
                        st.rerun()
                    else:
                        st.error("Could not add (asset with this name already exists).")
                except ValueError as ve:
                    st.error(str(ve))
                except Exception as e:
                    st.error(f"Failed to add asset: {e}")
            else:
                st.error("Please provide a valid company name and ticker.")

    if not df.empty:
        with st.expander("✎  Edit amounts & quantities"):
            all_cols = list(df.columns)
            default_cols = ["Name", "Invested (₹)", "Quantity", "Current Value (₹)", "P&L (₹)", "P&L %"]
            
            st.markdown("<div style='font-size:0.8rem;color:var(--q-text-3);margin-bottom:8px;'>Select columns to view/edit:</div>", unsafe_allow_html=True)
            selected_cols = st.multiselect("Visible Columns", options=all_cols, default=default_cols, key="ov_edit_cols", label_visibility="collapsed")
            
            # Always ensure the editable/identifier columns are present so the save logic doesn't crash
            for req in ["Name", "Invested (₹)", "Quantity"]:
                if req not in selected_cols:
                    selected_cols.insert(0, req)
                    
            # Deduplicate while preserving order
            seen = set()
            display_cols = [x for x in selected_cols if not (x in seen or seen.add(x))]
            
            _editor_key = "portfolio_editor_" + "_".join(display_cols)
            edited_df = st.data_editor(
                df[display_cols].copy(), use_container_width=True,
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
                disabled=[c for c in display_cols if c not in ["Invested (₹)", "Quantity"]],
                hide_index=True, key=_editor_key,
            )
            changes_made = False
            has_error = False
            for idx2, row in edited_df.iterrows():
                if df.loc[idx2, "Invested (₹)"] != row["Invested (₹)"] or df.loc[idx2, "Quantity"] != row["Quantity"]:
                    try:
                        update_asset_holdings(row["Name"], float(row["Invested (₹)"]), float(row["Quantity"]))
                        changes_made = True
                    except ValueError as ve:
                        st.error(f"Failed to update {row['Name']}: {ve}")
                        has_error = True
            
            if changes_made and not has_error:
                st.success("Saved!")
                time.sleep(0.5)
                st.rerun()
            elif changes_made and has_error:
                st.warning("Some changes were saved, but others failed.")
                time.sleep(1.5)
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

