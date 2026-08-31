import streamlit as st
import edu_db

def render(user_info):
    st.markdown("""
<style>
/* Hide the entire sidebar when on the Hub */
[data-testid="stSidebar"] {
    display: none;
}
.hub-header {
    text-align: center;
    margin-top: 3rem;
    margin-bottom: 3rem;
}
.hub-header h1 {
    font-weight: 700;
    font-size: 2.5rem;
    color: var(--q-text);
    margin-bottom: 0.5rem;
}
.hub-header p {
    font-size: 1.2rem;
    color: var(--q-text-3);
}
.hub-card {
    background-color: var(--q-bg-surface);
    border: 1px solid var(--q-border);
    border-radius: 12px;
    padding: 2rem;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.hub-card-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--q-text);
    margin-bottom: 0.5rem;
}
.hub-card-subtitle {
    font-size: 0.9rem;
    color: var(--q-text-3);
    margin-bottom: 2rem;
}
.hub-stat {
    background: rgba(255,255,255,0.03);
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
}
.hub-stat-label {
    font-size: 0.8rem;
    color: var(--q-text-3);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.hub-stat-value {
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--q-text);
}
</style>
""", unsafe_allow_html=True)

    st.markdown(f'<div class="hub-header"><h1>Welcome back, {user_info.get("display_name", "User")}.</h1><p>Where would you like to go today?</p></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        html_str1 = f'<div class="hub-card" style="margin-bottom: 1rem;"><div class="hub-card-title">💼 Professional Portfolio</div><div class="hub-card-subtitle">Track markets. Analyze risk. Grow your wealth.</div><div class="hub-stat"><div class="hub-stat-label">Status</div><div class="hub-stat-value" style="color: #60a5fa;">Active Environment</div></div></div>'
        st.markdown(html_str1, unsafe_allow_html=True)
        if st.button("Go to Portfolio ->", key="btn_go_portfolio", use_container_width=True, type="primary"):
            st.query_params["page"] = "Overview"
            st.rerun()

    with col2:
        progress = edu_db.load_progress()
        xp = progress.get("total_xp", 0)
        curr_lvl = progress.get("current_level", "Level 1")
        bal = progress.get("virtual_balance", 15000)

        html_str2 = f'<div class="hub-card" style="margin-bottom: 1rem;"><div class="hub-card-title">🎓 Games & Education</div><div class="hub-card-subtitle">Learn. Play. Achieve. Level up your skills.</div><div class="hub-stat" style="display:flex; justify-content:space-between; align-items:center;"><div><div class="hub-stat-label">Your Progress</div><div class="hub-stat-value" style="color: #facc15;">⭐ {xp} XP</div></div><div style="text-align: right;"><div class="hub-stat-label">Up Next</div><div class="hub-stat-value">▶️ {curr_lvl}</div></div></div><div class="hub-stat"><div class="hub-stat-label">Virtual Trading Balance</div><div class="hub-stat-value" style="color: #34d399;">₹ {bal:,.0f}</div></div></div>'
        st.markdown(html_str2, unsafe_allow_html=True)
        if st.button("Resume Learning ->", key="btn_go_education", use_container_width=True, type="primary"):
            st.query_params["page"] = "Edu_Overview"
            st.rerun()
