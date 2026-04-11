import streamlit as st

# Configure the personal workspace
st.set_page_config(
    page_title="My Dashboard", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# Define each app (Routine app has been removed)
money_location_page = st.Page("money_location.py", title="Money & Location", icon="📍", default=True)
strong_page = st.Page("strong.py", title="Strong Tracker", icon="💪")

# Create the navigation menu
pg = st.navigation([money_location_page, strong_page])

# Run the navigation router
pg.run()
