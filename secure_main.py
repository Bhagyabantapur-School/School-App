import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import threading
import pytz
from streamlit.runtime.scriptrunner import add_script_run_ctx

# ==========================================
# 1. GLOBAL PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="My Unified Hub",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. USER AUTHENTICATION DICTIONARY
# ==========================================
USERS = {
    "admin": {"name": "SUKHAMAY KISKU", "role": "admin", "password": "bpsAPP@2026"}, 
    "tr": {"name": "TAPASI RANA", "role": "teacher", "password": "tr26"}, 
    "sbr": {"name": "SUJATA BISWAS ROTHA", "role": "teacher", "password": "sbr26"}, 
    "rs": {"name": "ROHINI SINGH", "role": "teacher", "password": "rs26"}, 
    "unj": {"name": "UDAY NARAYAN JANA", "role": "teacher", "password": "unj26"}, 
    "bkp": {"name": "BIMAL KUMAR PATRA", "role": "teacher", "password": "bkp26"}, 
    "sp": {"name": "SUSMITA PAUL", "role": "teacher", "password": "sp26"}, 
    "tkm": {"name": "TAPAN KUMAR MANDAL", "role": "teacher", "password": "tkm26"}, 
    "mk": {"name": "MANJUMA KHATUN", "role": "teacher", "password": "mk26"}
}

# ==========================================
# 3. SESSION STATE INITIALIZATION
# ==========================================
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_role' not in st.session_state: st.session_state.user_role = None
if 'user_name' not in st.session_state: st.session_state.user_name = None

# ==========================================
# 4. LOGIN SCREEN (GATEKEEPER)
# ==========================================
if not st.session_state.authenticated:
    # Hide the sidebar completely on the login screen
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    
    st.markdown("<div class='login-box'><h3>🔐 System Login</h3><p>Please enter your Username & Password.</p></div>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        # Automatically format username inputs to lowercase and strip spaces
        ui = st.text_input("Username").lower().strip() 
        pi = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            # Verify credentials against the dictionary
            if ui in USERS and pi == USERS[ui]["password"]:
                st.session_state.authenticated = True
                st.session_state.user_role = USERS[ui]["role"]
                st.session_state.user_name = USERS[ui]["name"]
                st.rerun() 
            else: 
                st.error("❌ Incorrect Credentials")
    
    st.stop() # Halts all further script execution until logged in

# ==========================================
# --- AUTHENTICATED SYSTEM STARTS HERE ---
# ==========================================

# Sidebar Logout & Welcome
st.sidebar.success(f"👋 Welcome, {st.session_state.user_name}")
if st.sidebar.button("Log Out"): 
    st.session_state.authenticated = False 
    st.rerun()
st.sidebar.markdown("---")

# APP DICTIONARIES
personal_apps = [
    "Live Routine Hub", "Money & Location", "Money Utilities", "Strong Tracker", 
    "Project App", "Election Duty", "Monthly Tracker", "Money Tracker", 
    "Product Inventory", "Health Hub", "Backup Tracker", "Routine Audit", 
    "Routine Editor", "MDM Returns", "Video Manager", "Trace Inventory", 
    "Sleep & Water", "Packing Tracker", "App Updater", "Visual Dashboard"
]

bps_admin_apps = [
    "Main Dashboard", "Admission Hub", "Student Profiles", "ID Card Generator",
    "School Data", "Exam & Fees", "Library Manager", "Leave Management",
    "Distributions", "Returns", "Form Manager", "Staff Portal", "Grocery Manager"
]

bps_teacher_apps = [
    "Staff Portal", "Student Profiles", "Library Manager", 
    "Leave Management", "Distributions", "Returns", "Form Manager"
]

all_apps = personal_apps + bps_admin_apps + bps_teacher_apps

# ==========================================
# GLOBAL SHEET CONNECTION (DYNAMIC ROUTING)
# ==========================================
@st.cache_resource
def get_tracker_sheet(role):
    """Creates a connection, dynamically routing Admin vs Teacher data."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    
    if role == "admin":
        return client.open("Personal_Dashboard_Data").worksheet("Tracker")
    else:
        return client.open("BPS_Database").worksheet("Teacher_Tracker")

# ==========================================
# ASYNCHRONOUS TRACKER & PERSISTENCE
# ==========================================
@st.cache_data(ttl=300, show_spinner=False)
def get_last_opened_app(role):
    try:
        sheet = get_tracker_sheet(role)
        records = sheet.get_all_records()
        latest_app = "Live Routine Hub" if role == "admin" else "Staff Portal"
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
        return "Live Routine Hub" if role == "admin" else "Staff Portal"

def log_app_change_bg(app_name, role):
    sheet = get_tracker_sheet(role)
    
    def _log():
        try:
            ist = pytz.timezone('Asia/Kolkata')
            now_str = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
            
            all_rows = sheet.get_all_values()
            found_row = None
            clean_target = str(app_name).strip().upper()
            
            for idx, row in enumerate(all_rows):
                if row and str(row[0]).strip().upper() == clean_target:
                    found_row = idx + 1 
                    break
            
            if found_row:
                sheet.update_cell(found_row, 2, now_str)
            else:
                next_row = len(all_rows) + 1
                try:
                    sheet.update(range_name=f"A{next_row}:B{next_row}", values=[[app_name, now_str]], value_input_option="USER_ENTERED")
                except TypeError:
                    sheet.update(f"A{next_row}:B{next_row}", [[app_name, now_str]], value_input_option="USER_ENTERED")
                    
        except Exception as e:
            print(f"Background Logging Failed: {e}")
            
    thread = threading.Thread(target=_log)
    add_script_run_ctx(thread) 
    thread.start()

# ==========================================
# STATE MANAGEMENT
# ==========================================
role = st.session_state.user_role

if 'last_opened_app' not in st.session_state:
    st.session_state.last_opened_app = get_last_opened_app(role)

if 'current_tracked_app' not in st.session_state:
    st.session_state.current_tracked_app = st.session_state.last_opened_app

# ==========================================
# ROUTING LOGIC & WORKSPACE SWITCHER
# ==========================================
if role == "admin":
    if 'active_system' not in st.session_state:
        if st.session_state.last_opened_app in bps_admin_apps:
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
else:
    # Teachers are hard-locked to the BPS Digital System
    system_choice = 'BPS Digital System'

def is_default(app_name, system_category):
    last_app = st.session_state.last_opened_app
    if role == "teacher":
        if last_app not in bps_teacher_apps: last_app = "Staff Portal"
        return last_app == app_name
        
    if system_choice == system_category and last_app == app_name:
        return True
    if system_choice == system_category and last_app not in (personal_apps if system_choice == 'Personal Hub' else bps_admin_apps):
        if system_category == 'Personal Hub' and app_name == "Live Routine Hub": return True
        if system_category == 'BPS Digital System' and app_name == "Main Dashboard": return True
    return False

# ==========================================
# DEFINE PAGES
# ==========================================
# Personal Pages
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
app_updater = st.Page("app_update.py", title="App Updater", icon="🔄", default=is_default("App Updater", "Personal Hub"))
visual_dashboard = st.Page("dashboard.py", title="Visual Dashboard", icon="🚀", default=is_default("Visual Dashboard", "Personal Hub"))

# BPS Pages
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
grocery_app = st.Page("bps_grocery_ad.py", title="Grocery Manager", icon="🥦", default=is_default("Grocery Manager", "BPS Digital System"))

# ==========================================
# EXECUTE NAVIGATION MENU
# ==========================================
if role == "admin":
    if system_choice == 'Personal Hub':
        pg = st.navigation({
            "My Personal Hub": [
                routine_hub, money_location, money_utilities, strong, project, election, 
                monthly, money_tracker, product_inventory, health, backup, routine_audit, 
                routine_editor, mdm_return, ytfb_videos, trace_app, sleep_water, 
                packing_tracker, app_updater, visual_dashboard
            ]
        })
        st.sidebar.caption("🔒 Personal Workspace Active")
    else:
        pg = st.navigation({
            "System Home": [bps_dashboard],
            "Staff & Admin": [staff_portal],
            "Student Management": [admission, student_profile, id_card],
            "Academics & Finance": [school_data, exam_fees, library_app],
            "Operations": [leave, distribution, returns, form_manager, grocery_app]
        })
        st.sidebar.markdown("#### Bhagyabantapur Primary School")
        st.sidebar.caption("Head Teacher Dashboard Active")
else:
    # Restricted Teacher Navigation
    pg = st.navigation({
        "Dashboard": [staff_portal],
        "Academics": [student_profile, library_app],
        "Operations": [leave, distribution, returns, form_manager]
    })
    st.sidebar.markdown("#### Bhagyabantapur Primary School")
    st.sidebar.caption("Assistant Teacher Portal")

# ==========================================
# MASTER LOGGING TRIGGER
# ==========================================
if pg.title != st.session_state.current_tracked_app and pg.title in all_apps:
    st.session_state.current_tracked_app = pg.title
    st.session_state.last_opened_app = pg.title
    log_app_change_bg(pg.title, role)

# RUN NAVIGATION
pg.run()
