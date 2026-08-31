import streamlit as st
import edu_db

MODULES = [
    {
        "id": "level_1",
        "title": "Level 1: First ₹1,000",
        "description": "Start Investing. Absolute basics: what investing is, why start small, opening a demat.",
        "videos": [
            {"title": "What is Investing? Basics for Beginners", "creator": "Zerodha Varsity"},
            {"title": "How to Open a Demat Account in India", "creator": "Pranjal Kamra"},
            {"title": "Investing with Just ₹1,000 — Where to Start", "creator": "Warikoo"}
        ]
    },
    {
        "id": "level_2",
        "title": "Level 2: Grow Your Money",
        "description": "Compounding, SIP mechanics, saving vs investing, inflation.",
        "videos": [
            {"title": "Power of Compounding Explained", "creator": "CA Rachana Ranade"},
            {"title": "SIP vs Lumpsum — What Works Better", "creator": "Groww"},
            {"title": "Emergency Fund — How Much and Where to Park", "creator": "Labour Law Advisor"}
        ]
    },
    {
        "id": "level_3",
        "title": "Level 3: Reach Your Goal",
        "description": "Goal-based investing, financial planning, time horizons.",
        "videos": [
            {"title": "Goal Based Investing — Complete Framework", "creator": "CA Rachana Ranade"},
            {"title": "Retirement Planning — Start at 25 vs 35", "creator": "Pranjal Kamra"},
            {"title": "How to Reverse Engineer Your Financial Goal", "creator": "Akshat Shrivastava"}
        ]
    }
]

def render(user_info):
    st.markdown("""
    <style>
    .edu-header { padding: 2rem 0; border-bottom: 1px solid var(--q-border); margin-bottom: 2rem; }
    .edu-title { font-size: 2rem; font-weight: 700; color: var(--q-text); }
    .edu-subtitle { color: var(--q-text-3); font-size: 1.1rem; }
    .module-title { font-size: 1.4rem; font-weight: 600; color: #60a5fa; margin-bottom: 0.5rem; margin-top: 2rem;}
    .module-desc { color: var(--q-text-3); margin-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)
    
    if st.button("← Back to Hub", key="back_to_hub_edu"):
        st.query_params["page"] = "Hub"
        st.rerun()

    st.markdown('''
    <div class="edu-header">
        <div class="edu-title">🎓 Learning Modules</div>
        <div class="edu-subtitle">Watch curated long-form videos to earn XP and Virtual Trading Cash.</div>
    </div>
    ''', unsafe_allow_html=True)

    for mod in MODULES:
        st.markdown(f'<div class="module-title">{mod["title"]}</div><div class="module-desc">{mod["description"]}</div>', unsafe_allow_html=True)
        
        for idx, vid in enumerate(mod["videos"]):
            with st.container():
                col1, col2 = st.columns([4, 1], gap="medium")
                with col1:
                    st.markdown(f"**▶️ {vid['title']}**<br><span style='color:gray; font-size:0.85rem;'>{vid['creator']}</span>", unsafe_allow_html=True)
                with col2:
                    if st.button("Watch (+50 XP)", key=f"watch_{mod['id']}_{idx}", use_container_width=True):
                        st.success(f"Video unlocked! (XP would be added here)")
            st.markdown("<hr style='border-color: rgba(255,255,255,0.05); margin: 0.5rem 0;'>", unsafe_allow_html=True)
