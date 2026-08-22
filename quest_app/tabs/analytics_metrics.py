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
    st.subheader("Academic Visibility — Under the Hood")
    st.markdown("This section exposes the raw linear algebra operations running on your portfolio.")

    if not df.empty and summary.get("returns_df") is not None and not summary["returns_df"].empty:
        import numpy as np
        import pandas as pd
        import plotly.graph_objects as go

        returns_df = summary["returns_df"]
        # Convert to numpy array A (time periods x assets)
        A = returns_df.values
        asset_names = returns_df.columns.tolist()

        # --- SECTION 1 ---
        st.markdown("---")
        st.markdown("### SECTION 1 — QR Decomposition")
        st.markdown("##### QR Decomposition — Return Matrix Factorisation")
        st.markdown("<p style='font-family: \"JetBrains Mono\", Courier, monospace; font-size: 1.2rem; font-weight: 600; color: #38bdf8;'>A = QR  <span style='color: #94a3b8; font-size: 1rem; font-weight: 400;'>(where Q is orthogonal (QᵀQ = I) and R is upper triangular)</span></p>", unsafe_allow_html=True)
        st.markdown("We apply QR decomposition to the asset returns matrix A (rows = time periods, columns = assets). This separates the returns into an orthogonal basis Q and an upper triangular matrix R. The QR algorithm is also the numerical method used to extract eigenvalues in the next section.")

        # Compute QR
        Q, R = np.linalg.qr(A)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Q Matrix (Orthogonal Basis)**")
            q_display = pd.DataFrame(Q[:5, :5])
            if Q.shape[0] > 5 or Q.shape[1] > 5:
                st.caption(f"showing first {min(5, Q.shape[0])} periods × {min(5, Q.shape[1])} assets")
            st.dataframe(q_display.style.format("{:.4f}"), use_container_width=True)

        with c2:
            st.markdown("**R Matrix (Upper Triangular)**")
            r_display = pd.DataFrame(R[:5, :5])
            if R.shape[0] > 5 or R.shape[1] > 5:
                st.caption(f"showing first {min(5, R.shape[0])} periods × {min(5, R.shape[1])} assets")
            st.dataframe(r_display.style.format("{:.4f}"), use_container_width=True)

        st.markdown("**Verification: QᵀQ ≈ I**")
        qtq = np.dot(Q.T, Q)
        qtq_display = pd.DataFrame(qtq[:5, :5])
        st.dataframe(qtq_display.style.format("{:.4f}"), use_container_width=True)

        # --- SECTION 2 ---
        st.markdown("---")
        st.markdown("### SECTION 2 — Eigenvalue Extraction")
        st.markdown("##### Eigenvalue Analysis — Covariance Matrix Decomposition")
        st.markdown("<p style='font-family: \"JetBrains Mono\", Courier, monospace; font-size: 1.2rem; font-weight: 600; color: #ff4d6d;'>det(Σ - λI) = 0</p>", unsafe_allow_html=True)
        st.markdown("We compute the covariance matrix Σ from the asset returns, then solve the characteristic equation to find eigenvalues λ. Each eigenvalue represents the variance explained by one independent 'factor' driving the portfolio.")

        cov_matrix = returns_df.cov().values

        st.markdown("**Step 1 — Covariance Matrix Σ**")
        st.dataframe(pd.DataFrame(cov_matrix, index=asset_names, columns=asset_names).style.format("{:.6f}"), use_container_width=True)

        st.markdown("**Step 2 — QR Algorithm Iterations**")
        st.caption("Converging to diagonal form — diagonal entries become the eigenvalues.")

        A_k = cov_matrix.copy()
        for k in range(3):
            Q_k, R_k = np.linalg.qr(A_k)
            A_k = np.dot(R_k, Q_k)
            with st.expander(f"Iteration {k+1}: A_{k} = Q_{k}R_{k} → A_{k+1} = R_{k}Q_{k}"):
                st.dataframe(pd.DataFrame(A_k).style.format("{:.6f}"), use_container_width=True)

        st.markdown("**Step 3 — Extracted Eigenvalues**")
        eigenvalues = summary.get("pca_eigenvalues", [])
        explained_var = summary.get("pca_explained_var", [])

        for i, (eval_val, evar_val) in enumerate(zip(eigenvalues, explained_var)):
            st.markdown(f"**λ_{i+1} = {eval_val:.6f}** → explains **{evar_val*100:.2f}%** of portfolio variance")

        st.markdown("**Step 4 — Eigenvectors (Principal Components)**")
        eigenvectors = summary.get("pca_eigenvectors", [])
        if len(eigenvectors) > 0:
            top_k = min(3, len(eigenvectors[0]))
            eigen_df = pd.DataFrame(eigenvectors[:, :top_k], index=asset_names, columns=[f"Factor {i+1}" for i in range(top_k)])
            st.dataframe(eigen_df.style.format("{:.4f}"), use_container_width=True)

        # --- SECTION 3 ---
        st.markdown("---")
        st.markdown("### SECTION 3 — Factor Return Attribution")
        st.markdown("##### Factor Attribution — Systematic vs Idiosyncratic Returns")
        st.markdown("<p style='font-family: \"JetBrains Mono\", Courier, monospace; font-size: 1.2rem; font-weight: 600; color: #00ff87;'>Rᵢ = βᵢ · Rₘ + αᵢ + εᵢ</p>", unsafe_allow_html=True)
        st.markdown("Where: Rᵢ = return of asset i, Rₘ = market return (portfolio average), βᵢ = systematic risk coefficient (derived via QR-based least squares), αᵢ = idiosyncratic return, εᵢ = residual error")

        market_return = returns_df.mean(axis=1).values.reshape(-1, 1)
        X = np.hstack([np.ones((len(market_return), 1)), market_return])
        Q_x, R_x = np.linalg.qr(X)

        beta_data = []
        for i, asset in enumerate(asset_names):
            y = returns_df[asset].values.reshape(-1, 1)
            # Solve normal equations: R * beta = Q^T * y
            coeffs = np.linalg.solve(R_x, np.dot(Q_x.T, y))
            alpha, beta = coeffs[0][0], coeffs[1][0]

            var_total = np.var(y)
            var_sys = (beta**2) * np.var(market_return)
            sys_pct = min(1.0, var_sys / var_total) if var_total > 0 else 0.0
            idio_pct = 1.0 - sys_pct

            beta_data.append({
                "Asset": asset,
                "Beta": beta,
                "Systematic %": sys_pct * 100,
                "Idiosyncratic %": idio_pct * 100
            })

        beta_df = pd.DataFrame(beta_data)

        fig_beta = go.Figure()
        fig_beta.add_trace(go.Bar(
            y=beta_df["Asset"],
            x=beta_df["Systematic %"],
            name='Systematic (Market)',
            orientation='h',
            marker=dict(color='#38bdf8'),
            text=beta_df["Systematic %"].apply(lambda x: f"{x:.1f}%"),
            textposition='inside'
        ))
        fig_beta.add_trace(go.Bar(
            y=beta_df["Asset"],
            x=beta_df["Idiosyncratic %"],
            name='Idiosyncratic (Unique)',
            orientation='h',
            marker=dict(color='#00ff87'),
            text=beta_df["Idiosyncratic %"].apply(lambda x: f"{x:.1f}%"),
            textposition='inside'
        ))
        fig_beta.update_layout(
            barmode='stack',
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#94a3b8"),
            margin=dict(t=10, b=0, l=0, r=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False)
        )
        ui_theme.style_fig(fig_beta)
        st.plotly_chart(fig_beta, use_container_width=True)

        for _, row in beta_df.iterrows():
            st.markdown(f"**{row['Asset']}**: β = {row['Beta']:.2f} — {row['Systematic %']:.1f}% of its movement is explained by the overall market. Only {row['Idiosyncratic %']:.1f}% is unique to this asset.")

    else:
        st.info("Not enough historical data to run the Math Engine.")

