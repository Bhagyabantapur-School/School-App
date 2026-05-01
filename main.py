import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="My Personal Hub",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. Custom CSS for Beautiful Cards
st.markdown("""
<style>
    .main {
        background-color: #f0f2f6;
    }
    div[data-testid="stMetricValue"] {
        font-size: 25px;
    }
    .app-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #4F8BF9;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .app-card:hover {
        transform: scale(1.02);
    }
    .card-title {
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

# 3. Define the Dashboard Function (The Landing Page)
def show_dashboard():
    st.title("🚀 My Personal Dashboard")
    st.markdown("Welcome back! Here is a summary of your systems:")
    
    # Grid Layout: 3 columns for desktop
    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">📍 Money & Location</div>', unsafe_allow_html=True)
            st.metric("Latest Log", "Bhagyabantapur")
            if st.button("Open Money & Location", key="btn1"): st.switch_page(money_location_page)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">🗳️ Election Duty</div>', unsafe_allow_html=True)
            st.metric("Status", "Assigned")
            if st.button("Open Election Duty", key="btn4"): st.switch_page(election_page)
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">💪 Strong Tracker</div>', unsafe_allow_html=True)
            st.metric("Current Streak", "12 Days")
            if st.button("Open Strong", key="btn2"): st.switch_page(strong_page)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">📆 Monthly Summary</div>', unsafe_allow_html=True)
            st.metric("Month", "April 2026")
            if st.button("Open Monthly", key="btn5"): st.switch_page(monthly_page)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">💾 Backup Tracker</div>', unsafe_allow_html=True)
            st.metric("Last Backup", "2 Hours Ago")
            if st.button("Open Backup", key="btn8"): st.switch_page(backup_page)
            st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">🚀 Project App</div>', unsafe_allow_html=True)
            st.metric("Tasks Done", "85%")
            if st.button("Open Project", key="btn3"): st.switch_page(project_page)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">💵 Money Tracker</div>', unsafe_allow_html=True)
            st.metric("Wallet Balance", "₹ 4,250")
            if st.button("Open Money Tracker", key="btn6"): st.switch_page(money_tracker_page)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="app-card"><div class="card-title">❤️ Health Hub</div>', unsafe_allow_html=True)
            st.metric("Blood Pressure", "120/80")
            if st.button("Open Health", key="btn7"): st.switch_page(health_page)
            st.markdown('</div>', unsafe_allow_html=True)

# 4. Define all Page Links
# Note: The Dashboard is defined as a function here
dashboard_page = st.Page(show_dashboard, title="Visual Dashboard", icon="🚀", default=True)

money_location_page = st.Page("money_location.py", title="Money & Location", icon="📍")
strong_page = st.Page("strong.py", title="Strong Tracker", icon="💪")
project_page = st.Page("project_app.py", title="Project Tracker", icon="🚀")
election_page = st.Page("election_duty.py", title="Election Duty", icon="🗳️")
monthly_page = st.Page("monthly_app.py", title="Monthly Tracker", icon="📆")
money_tracker_page = st.Page("money_tracker.py", title="Money Tracker", icon="💵")
health_page = st.Page("health_app.py", title="Health Tracker", icon="❤️")
backup_page = st.Page("backup_tracker_app.py", title="Backup Tracker", icon="💾")

# 5. Run Navigation
pg = st.navigation([
    dashboard_page,
    money_location_page, 
    strong_page, 
    project_page, 
    election_page, 
    monthly_page, 
    money_tracker_page,
    health_page,
    backup_page
])

pg.run()
