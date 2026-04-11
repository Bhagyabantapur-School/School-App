import streamlit as st

# 1. Configure the main workspace (Must be the first Streamlit command)
st.set_page_config(
    page_title="BPS Digital", 
    page_icon="🏫", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Define each app as a separate page
# Ensure the filenames ('attendance.py', etc.) match exactly what is in your folder
attendance_page = st.Page("attendance.py", title="Attendance", icon="📅")
inventory_page = st.Page("inventory.py", title="Inventory", icon="📦")
profiles_page = st.Page("profiles.py", title="Student Profiles", icon="🧑‍🎓")
timeline_page = st.Page("timeline.py", title="Timeline", icon="⏱️")

# 3. Create the navigation menu
# You can group them into sections if you prefer by passing a dictionary, 
# but a simple list works perfectly for four core apps.
pg = st.navigation({
    "Daily Operations": [attendance_page, timeline_page],
    "Management": [profiles_page, inventory_page]
})

# 4. Add a global header or sidebar elements (Optional)
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ System Status: Online")

# 5. Run the navigation router
pg.run()
