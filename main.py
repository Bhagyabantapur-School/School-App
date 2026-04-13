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

# NEW: Define your project app
project_page = st.Page("project_app.py", title="Project Tracker", icon="🚀")

# Create the navigation menu (Added project_page to the list)
pg = st.navigation([money_location_page, strong_page, project_page])

# Run the navigation router
pg.run()
