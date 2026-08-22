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
    st.subheader("Visual Analytics")
    if not df.empty and df["Current Value (₹)"].sum() > 0:
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Portfolio Allocation (By Current Value)**")
            fig = px.pie(df[df["Current Value (₹)"] > 0], values='Current Value (₹)', names='Name', hole=0.62)
            # Clean look: percentages inside slices, hide labels for tiny ones
            fig.update_traces(
                textposition='inside', textinfo='percent', insidetextorientation='radial',
                texttemplate='%{percent:.0%}', sort=True,
                marker=dict(line=dict(color=ui_theme.palette()['bg'], width=2)),
            )
            fig.update_layout(
                margin=dict(t=0, b=0, l=0, r=0), uniformtext_minsize=10,
                uniformtext_mode='hide',
                legend=dict(orientation='v', y=0.5, font=dict(size=11)),
            )
            ui_theme.style_fig(fig)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("**Asset Correlation Matrix**")
            corr = summary.get("correlation_matrix", pd.DataFrame())
            if not corr.empty:
                fig2 = px.imshow(corr, text_auto=True, color_continuous_scale=['#1e3a5f', '#ffffff', '#7f1d1d'], range_color=[-1, 1], aspect='auto')
                fig2.update_xaxes(tickangle=45, tickfont=dict(size=12))
                fig2.update_yaxes(tickfont=dict(size=12))
                fig2.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=max(400, len(corr.columns) * 48), autosize=True)
                ui_theme.style_fig(fig2)
                st.plotly_chart(fig2, use_container_width=True)

                with st.expander("∑ Show Math"):
                    st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: ρ(X,Y) = Cov(X,Y) / (σₓ · σᵧ)</p>", unsafe_allow_html=True)
                    corr_mat = corr.copy()
                    _corr_vals = corr_mat.values.copy()
                    np.fill_diagonal(_corr_vals, -1.0)
                    corr_mat = pd.DataFrame(_corr_vals, index=corr_mat.index, columns=corr_mat.columns)
                    if not corr_mat.empty and len(corr_mat.columns) > 1:
                        max_idx = corr_mat.values.argmax()
                        r_idx, c_idx = np.unravel_index(max_idx, corr_mat.shape)
                        stock_x, stock_y = corr_mat.index[r_idx], corr_mat.columns[c_idx]
                        rho = corr_mat.iloc[r_idx, c_idx]
                        returns_df = summary.get("returns_df")
                        if returns_df is not None and not returns_df.empty:
                            cov_xy = returns_df[stock_x].cov(returns_df[stock_y])
                            std_x = returns_df[stock_x].std()
                            std_y = returns_df[stock_y].std()
                            st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Inputs:<br>Cov({stock_x}, {stock_y}) = {cov_xy:.6f}<br>σ_{stock_x} = {std_x:.6f}, σ_{stock_y} = {std_y:.6f}</p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: ρ = {rho:.4f}</p>", unsafe_allow_html=True)
                            st.markdown("A value above 0.7 means these assets move together 70%+ of the time.")
            else:
                st.info("Not enough data to calculate correlation yet.")

        st.markdown("---")
        st.markdown("### Diversification Health Check")
        st.markdown(f"Imagine your {len(df)} assets are {len(df)} musicians. True diversification means they're all playing different songs — so if one fails, the others carry the show. But if most of them are secretly following the same conductor (the broader market), then when the market crashes, ALL of them crash together. This check tells you how many independent songs are actually playing in your portfolio.")

        explained_var = summary.get("pca_explained_var", [])
        if len(explained_var) > 0:
            c3, c4 = st.columns(2)

            with c3:
                pca_df = pd.DataFrame({
                    "Hidden Force": [f"Force {i+1}" for i in range(len(explained_var))],
                    "Control %": explained_var * 100
                })
                # Show top 5 forces
                fig_pca = px.bar(pca_df.head(5), x="Hidden Force", y="Control %", text_auto='.1f', title="Forces Controlling Your Portfolio")
                fig_pca.update_traces(marker_color='#818cf8')
                fig_pca.update_layout(margin=dict(t=30, b=0, l=0, r=0))
                fig_pca.update_xaxes(showgrid=False)
                fig_pca.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
                ui_theme.style_fig(fig_pca)
                st.plotly_chart(fig_pca, use_container_width=True)

                with st.expander("∑ Show Math"):
                    st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: Σ = VΛVᵀ (eigendecomposition)</p>", unsafe_allow_html=True)
                    eigenvalues = summary.get("pca_eigenvalues", [])
                    if len(eigenvalues) >= 1:
                        l1 = eigenvalues[0]
                        l2 = eigenvalues[1] if len(eigenvalues) > 1 else 0
                        l3 = eigenvalues[2] if len(eigenvalues) > 2 else 0
                        sum_l = np.sum(eigenvalues)
                        st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Inputs: λ₁ = {l1:.6f}, λ₂ = {l2:.6f}, λ₃ = {l3:.6f}<br>Σλⱼ = {sum_l:.6f}</p>", unsafe_allow_html=True)
                        pct1 = (l1 / sum_l) * 100 if sum_l > 0 else 0
                        st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: Explained Variance % = λ₁ / Σλⱼ × 100 = {pct1:.2f}%</p>", unsafe_allow_html=True)

            with c4:
                top_factor_var = explained_var[0] * 100
                st.markdown(f"### **{top_factor_var:.1f}%**")
                st.markdown(f"**{top_factor_var:.1f}% of your portfolio's movement is controlled by a single hidden force** — most likely the overall Indian market direction.")

                st.markdown("<br>", unsafe_allow_html=True)

                if top_factor_var < 60:
                    st.success("🟢 **Good Diversification** — your stocks are behaving independently enough.")
                elif top_factor_var <= 75:
                    st.warning("🟡 **Moderate Risk** — most of your stocks rise and fall together. Consider adding assets from different sectors.")
                else:
                    st.error("🔴 **False Diversification** — you effectively own one position. A market crash will hit everything at once.")

        st.markdown("---")
        st.markdown("**Growth & Fall (Time Periods)**")
        perf_cols = ["Name", "1M Ret %", "6M Ret %", "1Y Ret %"]
        if all(c in df.columns for c in perf_cols):
            perf_df = df[perf_cols].copy()
            perf_df.set_index("Name", inplace=True)
            st.bar_chart(perf_df)

            with st.expander("∑ Show Math"):
                st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: Return % = (Pₜ - P₀) / P₀ × 100</p>", unsafe_allow_html=True)
                first_asset = df.iloc[0]
                # Approximation of P0 from current value and return
                pt = first_asset.get("Last Price", 0)
                pnl_pct = first_asset.get("P&L %", 0) / 100.0
                if pnl_pct != -1:
                    p0 = pt / (1 + pnl_pct)
                    ret_all = (pt - p0) / p0 * 100 if p0 > 0 else 0
                    st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Example ({first_asset['Name']}):<br>Inputs: P₀ = ₹{p0:.2f}, Pₜ = ₹{pt:.2f}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: Return % = {ret_all:.2f}%</p>", unsafe_allow_html=True)

