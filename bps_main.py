import streamlit as st

# 1. Configure the BPS workspace
st.set_page_config(
    page_title="BPS Digital", 
    page_icon="🏫", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. Define each app as a separate page
# Student Management
admission_page = st.Page("admission_hub.py", title="Admission Hub", icon="📝", default=True)
student_profile_page = st.Page("student_profile.py", title="Student Profiles", icon="🧑‍🎓")
id_card_page = st.Page("id_card_app.py", title="ID Card Generator", icon="🪪")

# Academics & Finance
school_data_page = st.Page("school_data.py", title="School Data", icon="📊")
exam_fees_page = st.Page("sch_exam_fees.py", title="Exam & Fees", icon="💰")

# Operations & Reports
leave_page = st.Page("leave_app.py", title="Leave Management", icon="🗓️")
distribution_page = st.Page("bps_distribution.py", title="Distributions", icon="🎒")
returns_page = st.Page("bps_returns.py", title="Returns", icon="📑")

# NEW: Define your Form Manager app
form_page = st.Page("form_manager.py", title="Form Manager", icon="📋")

# 3. Create the grouped navigation menu
pg = st.navigation({
    "Student Management": [admission_page, student_profile_page, id_card_page],
    "Academics & Finance": [school_data_page, exam_fees_page],
    "Operations": [leave_page, distribution_page, returns_page, form_page] # Added form_page here
})

# 4. Add school branding to the bottom of the sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("#### Bhagyabantapur Primary School")
st.sidebar.caption("BPS Digital Smart School System")

# 5. Run the navigation router
pg.run()
