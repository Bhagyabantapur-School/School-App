import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import threading
import pytz

# 1. GLOBAL PAGE CONFIGURATION
st.set_page_config(
    page_title="My Unified Hub",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. APP DICTIONARIES
personal_apps = [
    "Live Routine Hub", "Money & Location", "Money Utilities", "Strong Tracker", 
    "Project App", "Election Duty", "Monthly Tracker", "Money Tracker", 
    "Product Inventory", "Health Hub", "Backup Tracker", "Routine Audit", 
    "Routine Editor", "MDM Returns", "Video Manager", "Trace Inventory", 
    "Sleep & Water", "Packing Tracker", "Visual Dashboard"
]

bps_apps = [
    "Main Dashboard", "Admission Hub", "Student Profiles", "ID Card Generator",
    "School Data", "Exam & Fees", "Library Manager", "Leave Management",
    "Distributions", "Returns", "Form Manager", "Staff Portal"
]

all_apps = personal_apps + bps_apps

# ==========================================
# 3. GLOBAL SHEET CONNECTION (THE FIX)
# ==========================================
@st.cache_resource
def get_tracker_sheet():
    """Creates a SINGLE connection to Google Sheets that stays open globally."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("Personal_Dashboard_Data").worksheet("Tracker")

# ==========================================
# 4. ASYNCHRONOUS TRACKER & PERSISTENCE
# ==========================================
@st.cache_data(ttl=300, show_spinner=False)
def get_last_opened_app():
    """Fetches the most recently opened app to resume your session."""
    try:
        sheet = get_tracker_sheet()
        records = sheet.get_all_records()
        
        latest_app = "Live Routine Hub"
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

def log_app_change_bg(app_name):
    """Safely logs page changes using the globally cached sheet connection."""
    # We grab the cached sheet safely from the MAIN thread before entering the background
    sheet = get_tracker_sheet()
    
    def _log():
        try:
            ist = pytz.timezone('Asia/Kolkata')
            now_str = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
            
            # Fetch all values locally to save API calls and prevent search crashes
            all_rows = sheet.get_all_values()
            found_row = None
            for idx, row in enumerate(all_rows):
                if row and row[0] == app_name:
                    found_row = idx + 1 # Google Sheets is 1-indexed
                    break
            
            if found_row:
                sheet.update_cell(found_row, 2, now_str)
            else:
                sheet.append_row([app_name, now_str])
        except Exception as e:
            print(f"Background Logging Failed: {e}")
            
    threading.Thread(target=_log).start()

# ==========================================
# 5. STATE MANAGEMENT & ROUTING
# ==========================================
if 'last_opened_app' not in st.session_state:
    st.session_state.last_opened_app = get_last_opened_app()

if 'current_tracked_app' not in st.session_state:
    st.session_state.current_tracked_app = st.session_state.last_opened_app

if 'active_system' not in st.session_state:
    if st.session_state.last_opened_app in bps_apps:
        st.session_state.active_system = 'BPS Digital System'
    else:
        st.session_state.active_system = 'Personal Hub'

st.sidebar.markdown("### ⚙️ Workspace Switcher")
system_choice = st.sidebar.radio(
    "Select your environment:",
    ['Personal Hub', 'BPS Digital System'],
    index=0 if st.session_state.active_system == 'Personal Hub' else 1
)
st.session_state.active_system = system_choice
st.sidebar.markdown("---")

def is_default(app_name, system_category):
    last_app = st.session_state.last_opened_app
    if system_choice == system_category and last_app == app_name:
        return True
    if system_choice == system_category and last_app not in (personal_apps if system_choice == 'Personal Hub' else bps_apps):
        if system_category == 'Personal Hub' and app_name == "Live Routine Hub": 
            return True
        if system_category == 'BPS Digital System' and app_name == "Main Dashboard": 
            return True
    return False

# ==========================================
# 6. DEFINE ALL PAGES
# ==========================================
# --- Personal Pages ---
routine_hub = st.Page("routine_app.py", title="Live Routine Hub", icon="⏱️", default=is_default("Live Routine Hub", "Personal Hub"))
money_location = st.Page("money_location.py", title="Money & Location", icon="📍", default=is_default("Money & Location", "Personal Hub"))
money_utilities = st.Page("money_utilities.py", title="Money Utilities", icon="💳", default=is_default("Money Utilities", "Personal Hub")) 
strong = st.Page("strong.py", title="Strong Tracker", icon="💪", default=is_default("Strong Tracker", "Personal Hub"))
project = st.Page("project_app.py", title="Project App", icon="🚀", default=is_default("Project App", "Personal Hub"))
election = st.Page("election_duty.py", title="Election Duty", icon="🗳️", default=is_default("Election Duty", "Personal Hub"))
monthly = st.Page("monthly_app.py", title="Monthly Tracker", icon="📆", default=is_default("Monthly Tracker", "Personal Hub"))
money_tracker = st.Page("money_tracker.py", title="Money Tracker", icon="💵", default=is_default("Money Tracker", "Personal Hub"))
product_inventory = st.Page("product_inventory.py", title="Product Inventory", icon="📦", default=is_default("Product Inventory", "Personal Hub"))
health = st.Page("health_app.py", title="Health Hub", icon="❤️", default=is_default("Health Hub", "Personal Hub"))
backup = st.Page("backup_tracker_app.py", title="Backup Tracker", icon="💾", default=is_default("Backup Tracker", "Personal Hub"))
routine_audit = st.Page("routine_audit.py", title="Routine Audit", icon="🔍", default=is_default("Routine Audit", "Personal Hub"))
routine_editor = st.Page("routine_editor.py", title="Routine Editor", icon="✏️", default=is_default("Routine Editor", "Personal Hub"))
mdm_return = st.Page("mdm_return_log.py", title="MDM Returns", icon="📦", default=is_default("MDM Returns", "Personal Hub"))
ytfb_videos = st.Page("bps_ytfb_videos.py", title="Video Manager", icon="🎬", default=is_default("Video Manager", "Personal Hub"))
trace_app = st.Page("trace.py", title="Trace Inventory", icon="🏷️", default=is_default("Trace Inventory", "Personal Hub"))
sleep_water = st.Page("sleep_water_app.py", title="Sleep & Water", icon="💧", default=is_default("Sleep & Water", "Personal Hub"))
packing_tracker = st.Page("packing_app.py", title="Packing Tracker", icon="🎒", default=is_default("Packing Tracker", "Personal Hub")) 
visual_dashboard = st.Page("dashboard.py", title="Visual Dashboard", icon="🚀", default=is_default("Visual Dashboard", "Personal Hub"))

# --- BPS Digital Pages ---
bps_dashboard = st.Page("bps_dashboard.py", title="Main Dashboard", icon="🏫", default=is_default("Main Dashboard", "BPS Digital System"))
admission = st.Page("admission_hub.py", title="Admission Hub", icon="📝", default=is_default("Admission Hub", "BPS Digital System"))
student_profile = st.Page("student_profile.py", title="Student Profiles", icon="🎓", default=is_default("Student Profiles", "BPS Digital System"))
id_card = st.Page("id_card_app.py", title="ID Card Generator", icon="🪪", default=is_default("ID Card Generator", "BPS Digital System"))
school_data = st.Page("school_data.py", title="School Data", icon="📊", default=is_default("School Data", "BPS Digital System"))
exam_fees = st.Page("sch_exam_fees.py", title="Exam & Fees", icon="💰", default=is_default("Exam & Fees", "BPS Digital System"))
library_app = st.Page("library_app.py", title="Library Manager", icon="📚", default=is_default("Library Manager", "BPS Digital System")) 
leave = st.Page("leave_app.py", title="Leave Management", icon="🗓️", default=is_default("Leave Management", "BPS Digital System"))
distribution = st.Page("bps_distribution.py", title="Distributions", icon="🎒", default=is_default("Distributions", "BPS Digital System"))
returns = st.Page("bps_returns.py", title="Returns", icon="📑", default=is_default("Returns", "BPS Digital System"))
form_manager = st.Page("form_manager.py", title="Form Manager", icon="📋", default=is_default("Form Manager", "BPS Digital System"))
staff_portal = st.Page("bps_digital_sk.py", title="Staff Portal", icon="🔐", default=is_default("Staff Portal", "BPS Digital System"))

if system_choice == 'Personal Hub':
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
        "Academics & Finance": [school_data, exam_fees, library_app],
        "Operations": [leave, distribution, returns, form_manager]
    })
    st.sidebar.markdown("#### Bhagyabantapur Primary School")
    st.sidebar.caption("Head Teacher Dashboard Active")

# ==========================================
# 7. MASTER LOGGING TRIGGER
# ==========================================
if pg.title != st.session_state.current_tracked_app and pg.title in all_apps:
    st.session_state.current_tracked_app = pg.title
    st.session_state.last_opened_app = pg.title
    log_app_change_bg(pg.title) # Instantly fires to Google using cached connection!

# 8. RUN NAVIGATION
pg.run()
