import streamlit as st

# Configure the personal workspace
st.set_page_config(
    page_title="My Dashboard", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# Define each app
money_location_page = st.Page("money_location.py", title="Money & Location", icon="📍", default=True)
strong_page = st.Page("strong.py", title="Strong Tracker", icon="💪")
project_page = st.Page("project_app.py", title="Project Tracker", icon="🚀")
election_page = st.Page("election_duty.py", title="Election Duty", icon="🗳️")
monthly_page = st.Page("monthly_app.py", title="Monthly Tracker", icon="📆")
money_tracker_page = st.Page("money_tracker.py", title="Money Tracker", icon="💵")

# NEW: Define your Health app
health_page = st.Page("health_app.py", title="Health Tracker", icon="❤️")

# Create the navigation menu (Added health_page to the list)
pg = st.navigation([
    money_location_page, 
    strong_page, 
    project_page, 
    election_page, 
    monthly_page, 
    money_tracker_page,
    health_page
])

# Run the navigation router
pg.run()
