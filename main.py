import streamlit as st

# Configure the personal workspace
st.set_page_config(
    page_title="My Dashboard", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="collapsed" # Starts closed, but the > button will be visible
)

# Define each app
routine_page = st.Page("routine_app.py", title="Routine Dashboard", icon="🏠", default=True)
money_location_page = st.Page("money_location.py", title="Money & Location", icon="📍")
strong_page = st.Page("strong.py", title="Strong Tracker", icon="💪")

# Create the navigation menu
pg = st.navigation([routine_page, money_location_page, strong_page])

# Run the navigation router
pg.run()
