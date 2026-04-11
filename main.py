import streamlit as st

# Configure the main workspace (Must be the first Streamlit command)
st.set_page_config(
    page_title="BPS Digital", 
    page_icon="🏫", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define each app as a separate page using your exact file names
money_location_page = st.Page("money_location.py", title="Money & Location", icon="📍")
routine_page = st.Page("routine_app.py", title="Routine Tracker", icon="📅")
strong_page = st.Page("strong.py", title="Strong", icon="💪")

# Create the navigation menu
pg = st.navigation([routine_page, money_location_page, strong_page])

# Add a global header or sidebar elements (Optional)
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ System Status: Online")

# Run the navigation router
pg.run()
