import streamlit as st

# 1. GLOBAL PAGE CONFIGURATION
st.set_page_config(
    page_title="My Unified Hub",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. STATE MANAGEMENT FOR SYSTEM TOGGLE
if 'active_system' not in st.session_state:
    st.session_state.active_system = 'Personal Hub'

# 3. THE SYSTEM SWITCHER (SIDEBAR)
st.sidebar.markdown("### ⚙️ Workspace Switcher")
system_choice = st.sidebar.radio(
    "Select your environment:",
    ['Personal Hub', 'BPS Digital System'],
    index=0 if st.session_state.active_system == 'Personal Hub' else 1
)
st.session_state.active_system = system_choice
st.sidebar.markdown("---")

# 4. DEFINE ALL PAGES
# --- Personal Pages ---
personal_dashboard = st.Page("dashboard.py", title="Visual Dashboard", icon="🚀", default=(system_choice == 'Personal Hub'))
money_location = st.Page("money_location.py", title="Money & Location", icon="📍")
strong = st.Page("strong.py", title="Strong Tracker", icon="💪")
project = st.Page("project_app.py", title="Project Tracker", icon="🚀")
election = st.Page("election_duty.py", title="Election Duty", icon="🗳️")
monthly = st.Page("monthly_app.py", title="Monthly Tracker", icon="📆")
money_tracker = st.Page("money_tracker.py", title="Money Tracker", icon="💵")
health = st.Page("health_app.py", title="Health Tracker", icon="❤️")
backup = st.Page("backup_tracker_app.py", title="Backup Tracker", icon="💾")
routine = st.Page("routine_app.py", title="Daily Routine", icon="⏱️")
routine_audit = st.Page("routine_audit.py", title="Routine Audit", icon="🔍") # <-- NEW
routine_editor = st.Page("routine_editor.py", title="Routine Editor", icon="✏️") # <-- NEW
mdm_return = st.Page("mdm_return_log.py", title="MDM Returns", icon="📦")
ytfb_videos = st.Page("bps_ytfb_videos.py", title="Video Manager", icon="🎬")

# --- BPS Digital Pages ---
bps_dashboard = st.Page("bps_dashboard.py", title="Main Dashboard", icon="🏫", default=(system_choice == 'BPS Digital System'))
admission = st.Page("admission_hub.py", title="Admission Hub", icon="📝")
student_profile = st.Page("student_profile.py", title="Student Profiles", icon="🧑‍🎓")
id_card = st.Page("id_card_app.py", title="ID Card Generator", icon="🪪")
school_data = st.Page("school_data.py", title="School Data", icon="📊")
exam_fees = st.Page("sch_exam_fees.py", title="Exam & Fees", icon="💰")
leave = st.Page("leave_app.py", title="Leave Management", icon="🗓️")
distribution = st.Page("bps_distribution.py", title="Distributions", icon="🎒")
returns = st.Page("bps_returns.py", title="Returns", icon="📑")
form_manager = st.Page("form_manager.py", title="Form Manager", icon="📋")
staff_portal = st.Page("bps_digital_sk.py", title="Staff Portal", icon="🔐")

# 5. DYNAMIC NAVIGATION LOGIC
if st.session_state.active_system == 'Personal Hub':
    # Load only the Personal Apps into the sidebar
    pg = st.navigation({
        "My Personal Hub": [
            personal_dashboard, money_location, strong, project, election, 
            monthly, money_tracker, health, backup, routine, 
            routine_audit, routine_editor, # <-- ADDED AFTER ROUTINE
            mdm_return, ytfb_videos
        ]
    })
    st.sidebar.caption("🔒 Personal Workspace Active")

else:
    # Load only the BPS Apps into the sidebar
    pg = st.navigation({
        "System Home": [bps_dashboard],
        "Staff & Admin": [staff_portal],
        "Student Management": [admission, student_profile, id_card],
        "Academics & Finance": [school_data, exam_fees],
        "Operations": [leave, distribution, returns, form_manager]
    })
    st.sidebar.markdown("#### Bhagyabantapur Primary School")
    st.sidebar.caption("Head Teacher Dashboard Active")

# 6. RUN NAVIGATION
pg.run()
