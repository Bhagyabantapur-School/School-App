import streamlit as st

# 1. Global Page Configuration
st.set_page_config(
    page_title="My Personal Hub",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. Define all pages pointing to ACTUAL FILES
pg = st.navigation([
    st.Page("dashboard.py", title="Visual Dashboard", icon="🚀", default=True),
    st.Page("money_location.py", title="Money & Location", icon="📍"),
    st.Page("strong.py", title="Strong Tracker", icon="💪"),
    st.Page("project_app.py", title="Project Tracker", icon="🚀"),
    st.Page("election_duty.py", title="Election Duty", icon="🗳️"),
    st.Page("monthly_app.py", title="Monthly Tracker", icon="📆"),
    st.Page("money_tracker.py", title="Money Tracker", icon="💵"),
    st.Page("health_app.py", title="Health Tracker", icon="❤️"),
    st.Page("backup_tracker_app.py", title="Backup Tracker", icon="💾"),
    st.Page("routine_app.py", title="Daily Routine", icon="⏱️") # <-- New Routine App
])

# 3. Run Navigation
pg.run()
