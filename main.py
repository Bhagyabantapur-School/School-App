import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. GLOBAL PAGE CONFIGURATION
st.set_page_config(
    page_title="My Unified Hub",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. PERSISTENT "LAST OPENED" LOGIC
@st.cache_data(ttl=300, show_spinner=False)
def get_last_opened_app():
    """Fetches the most recently opened app from Google Sheets to resume session."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open("Personal_Dashboard_Data").worksheet("Tracker")
        records = sheet.get_all_records()
        
        latest_app = "Live Routine Hub" # Default fallback
        latest_time = None
        
        for row in records:
            app_name = row.get('App Name', '')
            opened_str = str(row.get('Last Opened', ''))
            if opened_str:
                try:
                    opened_dt = datetime.strptime(opened_str, "%Y-%m-%d %H:%M:%S")
                    if latest_time is None or opened_dt > latest_time:
                        latest_time = opened_dt
                        latest_app = app_name
                except: pass
        return latest_app
    except:
        return "Live Routine Hub"

# STATE MANAGEMENT
if 'active_system' not in st.session_state:
    st.session_state.active_system = 'Personal Hub'

if 'last_opened_app' not in st.session_state:
    st.session_state.last_opened_app = get_last_opened_app()

# 3. THE SYSTEM SWITCHER (SIDEBAR)
st.sidebar.markdown("### ⚙️ Workspace Switcher")
system_choice = st.sidebar.radio(
    "Select your environment:",
    ['Personal Hub', 'BPS Digital System'],
    index=0 if st.session_state.active_system == 'Personal Hub' else 1
)
st.session_state.active_system = system_choice
st.sidebar.markdown("---")

# Helper function to dynamically set the correct default landing page
def is_default(app_name):
    return (system_choice == 'Personal Hub' and st.session_state.last_opened_app == app_name)

# 4. DEFINE ALL PAGES
# --- Personal Pages ---
routine_hub = st.Page("routine_app.py", title="Live Routine Hub", icon="⏱️", default=is_default("Live Routine Hub"))
money_location = st.Page("money_location.py", title="Money & Location", icon="📍", default=is_default("Money & Location"))
money_utilities = st.Page("money_utilities.py", title="Money Utilities", icon="💳", default=is_default("Money Utilities"))
strong = st.Page("strong.py", title="Strong Tracker", icon="💪", default=is_default("Strong Tracker"))
project = st.Page("project_app.py", title="Project Tracker", icon="🚀", default=is_default("Project App"))
election = st.Page("election_duty.py", title="Election Duty", icon="🗳️", default=is_default("Election Duty"))
monthly = st.Page("monthly_app.py", title="Monthly Tracker", icon="📆", default=is_default("Monthly Tracker"))
money_tracker = st.Page("money_tracker.py", title="Money Tracker", icon="💵", default=is_default("Money Tracker"))
product_inventory = st.Page("product_inventory.py", title="Product Inventory", icon="📦", default=is_default("Product Inventory"))
health = st.Page("health_app.py", title="Health Tracker", icon="❤️", default=is_default("Health Hub"))
backup = st.Page("backup_tracker_app.py", title="Backup Tracker", icon="💾", default=is_default("Backup Tracker"))
routine_audit = st.Page("routine_audit.py", title="Routine Audit", icon="🔍", default=is_default("Routine Audit"))
routine_editor = st.Page("routine_editor.py", title="Routine Editor", icon="✏️", default=is_default("Routine Editor"))
mdm_return = st.Page("mdm_return_log.py", title="MDM Returns", icon="📦", default=is_default("MDM Returns"))
ytfb_videos = st.Page("bps_ytfb_videos.py", title="Video Manager", icon="🎬", default=is_default("Video Manager"))
trace_app = st.Page("trace.py", title="Trace Inventory", icon="🏷️", default=is_default("Trace Inventory"))
sleep_water = st.Page("sleep_water_app.py", title="Sleep & Water", icon="💧", default=is_default("Sleep & Water"))
packing_tracker = st.Page("packing_app.py", title="Packing Tracker", icon="🎒", default=is_default("Packing Tracker"))
visual_dashboard = st.Page("dashboard.py", title="Visual Dashboard", icon="🚀", default=is_default("Visual Dashboard"))

# --- BPS Digital Pages ---
bps_dashboard = st.Page("bps_dashboard.py", title="Main Dashboard", icon="🏫", default=(system_choice == 'BPS Digital System'))
admission = st.Page("admission_hub.py", title="Admission Hub", icon="📝")
student_profile = st.Page("student_profile.py", title="Student Profiles", icon="🎓")
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
    pg = st.navigation({
        "My Personal Hub": [
            routine_hub, money_location, money_utilities, 
            strong, project, election, monthly, money_tracker, product_inventory,
            health, backup, routine_audit, routine_editor, 
            mdm_return, ytfb_videos, trace_app, sleep_water, packing_tracker, visual_dashboard
        ]
    })
    st.sidebar.caption("🔒 Personal Workspace Active")
else:
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
