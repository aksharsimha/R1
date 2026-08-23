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
    st.subheader("Actionable Recommendations")

    if not df.empty:
        total_val = summary.get('total_value', 1.0)
        import numpy as np

        # --- SECTION A ---
        st.markdown("### SECTION A — Buy / Sell / Hold Signals")
        signals_data = []
        avg_sharpe = df["Sharpe Ratio"].mean() if "Sharpe Ratio" in df.columns else 0

        for _, row in df.iterrows():
            name = row["Name"]
            pnl_perc = row.get("P&L %", 0)
            ret_1m = row.get("1M Ret %", 0)
            ret_6m = row.get("6M Ret %", 0)
            ret_1y = row.get("1Y Ret %", 0)
            sharpe = row.get("Sharpe Ratio", 0)

            if pnl_perc > 0 and ret_1m > 0 and sharpe > avg_sharpe:
                signal = "🟢 BUY"
                reason = f"Up {pnl_perc:.2f}% and showing positive momentum across recent timeframes."
            elif pnl_perc < -8 or (ret_1m < 0 and ret_6m < 0 and ret_1y < 0):
                signal = "🔴 SELL"
                if pnl_perc < -8:
                    reason = f"Has fallen {pnl_perc:.2f}%, breaking the -8% stop-loss threshold."
                else:
                    reason = "Consistently negative returns across 1M, 6M, and 1Y horizons."
            else:
                signal = "🟡 HOLD"
                reason = "No strong momentum signals in either direction. Continue monitoring."

            signals_data.append({
                "Asset": name,
                "Signal": signal,
                "Reason": reason
            })

        _sig_df = pd.DataFrame(signals_data)
        _sig_cols = st.multiselect("Visible Columns", options=_sig_df.columns, default=list(_sig_df.columns), key="insight_sig_cols", label_visibility="collapsed")
        if not _sig_cols: _sig_cols = list(_sig_df.columns)
        st.table(_sig_df[_sig_cols])
        st.markdown("---")

        # --- SECTION B ---
        st.markdown("### SECTION B — Rebalancing Suggestions")
        rebal_data = []
        for _, row in df.iterrows():
            name = row["Name"]
            val = row.get("Current Value (₹)", 0)
            pct = (val / total_val) * 100 if total_val > 0 else 0

            if pct > 25:
                action = "Overweight — consider trimming."
            elif pct < 3 and val > 0:
                action = "Underweight — consider increasing or removing."
            elif val > 0:
                action = "Optimal — no action needed."
            else:
                continue

            if val > 0:
                rebal_data.append({
                    "Asset": name,
                    "Current %": f"{pct:.1f}%",
                    "Target Range": "3% - 25%",
                    "Action": action
                })

        _reb_df = pd.DataFrame(rebal_data)
        if not _reb_df.empty:
            _reb_cols = st.multiselect("Visible Columns", options=_reb_df.columns, default=list(_reb_df.columns), key="insight_reb_cols", label_visibility="collapsed")
            if not _reb_cols: _reb_cols = list(_reb_df.columns)
            st.table(_reb_df[_reb_cols])
        st.markdown("---")

        # --- SECTION C ---
        st.markdown("### SECTION C — Risk Warnings in Plain English")

        # 1. Concentration Risk
        if not df.empty and total_val > 0:
            top_asset = df.loc[df["Current Value (₹)"].idxmax()]
            top_pct = (top_asset["Current Value (₹)"] / total_val) * 100
            loss_10_perc = top_asset["Current Value (₹)"] * 0.10
            st.warning(f"**Concentration Risk:** Your top holding **{top_asset['Name']}** makes up **{top_pct:.1f}%** of your portfolio. If it drops 10%, you lose **₹{loss_10_perc:,.2f}**.")

        # 2. Correlation Warning
        corr = summary.get("correlation_matrix", pd.DataFrame())
        corr_found = False
        if not corr.empty and len(corr.columns) > 1:
            for i in range(len(corr.columns)):
                for j in range(i+1, len(corr.columns)):
                    if corr.iloc[i, j] > 0.7:
                        stock_a = corr.columns[i]
                        stock_b = corr.columns[j]
                        st.error(f"**Correlation Warning:** **{stock_a}** and **{stock_b}** move almost identically (correlation > 0.7). Owning both gives you less protection than you think.")
                        corr_found = True

        # 3. Volatility Warning
        vol_found = False
        for _, row in df.iterrows():
            name = row["Name"]
            vol_ann = row.get("Volatility %", 0) / 100.0
            if pd.notna(vol_ann):
                daily_vol_perc = (vol_ann / np.sqrt(252)) * 100
                if daily_vol_perc > 3.0:
                    st.error(f"**Volatility Warning:** **{name}** is highly volatile. Its normal daily swing is over 3% of its price.")
                    vol_found = True

        if not corr_found and not vol_found:
            st.success("No extreme correlation or daily volatility risks detected. Your diversification is holding up well.")

        st.markdown("---")

        # --- SECTION D ---
        st.markdown("### SECTION D — What's Dragging Your Portfolio")
        if "P&L (₹)" in df.columns:
            sorted_df = df.sort_values(by="P&L (₹)", ascending=True)
            loser_count = 0
            for i, row in sorted_df.iterrows():
                name = row["Name"]
                pnl_rupees = row["P&L (₹)"]
                pnl_perc = row.get("P&L %", 0)

                if pnl_rupees < 0:
                    if loser_count == 0:
                        st.error(f"**{name} is your biggest drag** — it alone has cost you **₹{abs(pnl_rupees):,.2f}** ({pnl_perc:+.2f}% loss). It has been underperforming its historical average. Do not average down yet.")
                    else:
                        st.warning(f"**{name} is losing money** — down **₹{abs(pnl_rupees):,.2f}** ({pnl_perc:+.2f}%). Keep a close eye on this position.")
                    loser_count += 1
                elif pnl_rupees > 0:
                    st.success(f"**{name} is generating wealth** — up **₹{pnl_rupees:,.2f}** ({pnl_perc:+.2f}% gain). It is strongly contributing to your portfolio's growth.")

