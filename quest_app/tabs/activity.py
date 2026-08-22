import streamlit as st
import pandas as pd
import numpy as np
import datetime as _dt
import plotly.express as px
import plotly.graph_objects as go
import time
import ui_theme
from risk_analyzer import AssetType
from portfolio_ledger import add_asset, remove_asset, update_asset_holdings, get_transactions
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
    st.subheader("Transaction History")
    txs = get_transactions()
    if txs:
        tx_df = pd.DataFrame(txs)
        # Rearrange and format
        tx_df = tx_df[["timestamp", "action", "asset", "amount", "details"]]
        tx_df["amount"] = tx_df["amount"].apply(lambda x: f"₹ {x:,.2f}" if isinstance(x, (int, float)) else x)
        tx_df.columns = ["Timestamp", "Action", "Asset", "Amount", "Details"]
        st.dataframe(tx_df, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions logged yet.")

    st.markdown("---")
    st.markdown("### 🍔 Lifetime Asset Explorer")
    st.markdown("Select an asset from the dropdown menu to view its complete lifetime movement since inception.")

    if current_assets:
        asset_names = [asset.name for asset in current_assets]
        selected_lifetime_asset_name = st.selectbox("Select Asset", asset_names, key="lifetime_asset_select")
        selected_asset_obj = next((a for a in current_assets if a.name == selected_lifetime_asset_name), None)

        if selected_asset_obj:
            with st.spinner(f"Fetching lifetime data for {selected_lifetime_asset_name}..."):
                try:
                    import yfinance as yf
                    if selected_asset_obj.asset_type == AssetType.MUTUAL_FUND:
                        from risk_analyzer import fetch_mf_history
                        hist_df = fetch_mf_history(selected_asset_obj.identifier, lookback_years=20)
                    elif selected_asset_obj.asset_type == AssetType.DIGITAL_GOLD:
                        hist_df = yf.download("GOLDBEES.NS", period="max", progress=False, auto_adjust=True, multi_level_index=False)
                    else:
                        hist_df = yf.download(selected_asset_obj.identifier, period="max", progress=False, auto_adjust=True, multi_level_index=False)

                    if not hist_df.empty:
                        fig = px.line(hist_df, x=hist_df.index, y="Close")
                        fig.update_layout(
                            title=f"Lifetime Price History: {selected_lifetime_asset_name}",
                            xaxis_title="Date", 
                            yaxis_title="Price (₹)", 
                            margin=dict(t=40, b=0, l=0, r=0),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter", color="#94a3b8")
                        )
                        fig.update_xaxes(showgrid=False)
                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)')

                        # Add a beautiful gradient fill
                        fig.update_traces(line_color='#00ff87', fill='tozeroy', fillcolor='rgba(0, 255, 135, 0.1)')

                        ui_theme.style_fig(fig)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No historical data found for this asset.")
                except Exception as e:
                    st.error(f"Could not fetch history: {e}")

