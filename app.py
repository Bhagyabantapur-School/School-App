import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

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
# 2. USER AUTHENTICATION & INITIALS DICTIONARY
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

TEACHER_INITIALS = {
    "SUKHAMAY KISKU": "SK", 
    "TAPASI RANA": "TR", 
    "SUJATA BISWAS ROTHA": "SBR", 
    "ROHINI SINGH": "RS", 
    "UDAY NARAYAN JANA": "UNJ", 
    "BIMAL KUMAR PATRA": "BKP", 
    "SUSMITA PAUL": "SP", 
    "TAPAN KUMAR MANDAL": "TKM", 
    "MANJUMA KHATUN": "MK"
}

# ==========================================
# 3. GOOGLE SHEETS CONNECTORS
# ==========================================
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    )

@st.cache_resource
def init_routine_gsheet():
    try:
        return gspread.authorize(get_google_credentials()).open("bps_routine")
    except Exception:
        return None

@st.cache_resource
def init_database_gsheet():
    try:
        return gspread.authorize(get_google_credentials()).open("BPS_Database")
    except Exception:
        return None

@st.cache_data(ttl=300)
def fetch_routine_data():
    try:
        r_sh = init_routine_gsheet()
        if r_sh:
            df = pd.DataFrame(r_sh.sheet1.get_all_records()).replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_leave_data():
    try:
        db_sh = init_database_gsheet()
        if db_sh:
            ws = db_sh.worksheet("teacher_leave")
            df = pd.DataFrame(ws.get_all_records()).replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except Exception:
        pass
    return pd.DataFrame()

def parse_time_safe(t_str):
    for fmt in ('%H:%M', '%I:%M %p', '%H:%M:%S'):
        try:
            return datetime.strptime(str(t_str).strip(), fmt).time()
        except Exception:
            continue
    return None

# ==========================================
# 4. SESSION STATE INITIALIZATION
# ==========================================
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_role' not in st.session_state: st.session_state.user_role = None
if 'user_name' not in st.session_state: st.session_state.user_name = None

# ==========================================
# 5. LOGIN SCREEN (GATEKEEPER)
# ==========================================
if not st.session_state.authenticated:
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    
    st.markdown("<div class='login-box'><h3>🔐 System Login</h3><p>Please enter your Username & Password.</p></div>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        ui = st.text_input("Username").lower().strip() 
        pi = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            if ui in USERS and pi == USERS[ui]["password"]:
                st.session_state.authenticated = True
                st.session_state.user_role = USERS[ui]["role"]
                st.session_state.user_name = USERS[ui]["name"]
                st.rerun() 
            else: 
                st.error("❌ Incorrect Credentials")
    
    st.stop()

# ==========================================
# 6. SIDEBAR CONTROLS & MANUAL SYNC
# ==========================================
st.sidebar.success(f"👋 Welcome, {st.session_state.user_name}")

if st.sidebar.button("🔄 Sync Schedule", use_container_width=True, key="sync_routine_btn"):
    fetch_routine_data.clear()
    fetch_leave_data.clear()
    st.rerun()

if st.sidebar.button("Log Out", use_container_width=True): 
    st.session_state.authenticated = False 
    st.rerun()
st.sidebar.markdown("---")

# ==========================================
# 7. LIVE ROUTINE TRACKER BANNER
# ==========================================
def render_tracker():
    st.markdown("#### ⏱️ My Live Class")
    
    utc_now = datetime.now(timezone.utc)
    now = utc_now + timedelta(hours=5, minutes=30)
    curr_time = now.time()
    tdy = now.strftime('%A')
    curr_date_str = now.strftime('%d-%m-%Y')
    
    rout = fetch_routine_data()
    ll = fetch_leave_data()
    mc = TEACHER_INITIALS.get(st.session_state.user_name, st.session_state.user_name)
    
    # 1. Check if logged-in user is ON LEAVE or PARTIAL SHIFT today
    is_fully_on_leave = False
    given_away_slots = []
    leave_type = ""
    
    if not ll.empty and 'Date' in ll.columns and 'Teacher' in ll.columns:
        user_leave = ll[(ll['Date'].astype(str).str.strip() == curr_date_str) & (ll['Teacher'].astype(str).str.strip() == st.session_state.user_name)]
        if not user_leave.empty:
            leave_type = str(user_leave.iloc[0].get('Type', 'Leave'))
            # If they are shifted, find out exactly which slots they abandoned
            if leave_type in ['Class Shift / Internal Duty', 'Half Day']:
                given_away_slots = [a.split(": ")[0].strip() for a in str(user_leave.iloc[0].get('Detailed_Sub_Log', '')).split(" | ") if ": " in a and "None" not in a]
            else:
                is_fully_on_leave = True
            
    if is_fully_on_leave:
        st.warning(f"🏖️ You are marked on leave today ({leave_type}). Regular classes are hidden.")
        ms = pd.DataFrame()
    else:
        # 2. Get Default Regular Schedule and strip out abandoned shift classes
        ms = rout[(rout['Teacher'] == mc) & (rout['Day'] == tdy)].copy() if not rout.empty else pd.DataFrame()
        if not ms.empty:
            ms['Is_Sub'] = False
            if given_away_slots:
                ms = ms[~ms['Start_Time'].astype(str).str.strip().isin(given_away_slots)]
        
        # 3. Check and Merge Today's Substitution Assignments (Supports Emojis Stripping)
        sd = []
        if not ll.empty and 'Date' in ll.columns and not rout.empty:
            for _, r in ll[ll['Date'].astype(str).str.strip() == curr_date_str].iterrows():
                sub_log = str(r.get('Detailed_Sub_Log', ''))
                absent_teacher = str(r.get('Teacher', '')).strip()
                absent_initials = TEACHER_INITIALS.get(absent_teacher, absent_teacher)
                
                for item in sub_log.split(" | "):
                    if ": " in item:
                        slot, sub_n = item.rsplit(": ", 1)
                        clean_sub_n = sub_n.replace('✅', '').replace('⚠️', '').replace('⛔', '').replace('🚫', '').strip()
                        if clean_sub_n == st.session_state.user_name:
                            oc = rout[(rout['Teacher'] == absent_initials) & (rout['Day'] == tdy) & (rout['Start_Time'].astype(str).str.strip() == slot.strip())]
                            if not oc.empty:
                                rx = oc.iloc[0]
                                sd.append({
                                    'Start_Time': rx['Start_Time'],
                                    'End_Time': rx['End_Time'],
                                    'Class': rx['Class'],
                                    'Section': rx.get('Section', 'A'),
                                    'Subject': f"🔄 {rx['Subject']} (Sub for {absent_initials})",
                                    'Teacher': mc,
                                    'Day': tdy,
                                    'Is_Sub': True
                                })
        
        if sd:
            ms = pd.concat([ms, pd.DataFrame(sd)], ignore_index=True)
    
    prev_rows, curr_rows, next_rows = [], [], []
    
    if not ms.empty:
        ms['Start_Obj'] = ms['Start_Time'].apply(parse_time_safe)
        ms['End_Obj'] = ms['End_Time'].apply(parse_time_safe)
        ms = ms.dropna(subset=['Start_Obj', 'End_Obj']).sort_values('Start_Obj')
        
        past_slots = ms[ms['End_Obj'] < curr_time]['Start_Obj']
        latest_past_slot = past_slots.max() if not past_slots.empty else None
        
        future_slots = ms[ms['Start_Obj'] > curr_time]['Start_Obj']
        earliest_future_slot = future_slots.min() if not future_slots.empty else None
        
        for _, r in ms.iterrows():
            st_obj = r['Start_Obj']
            et_obj = r['End_Obj']
            
            if st_obj <= curr_time <= et_obj:
                curr_rows.append(r)
            elif latest_past_slot and st_obj == latest_past_slot and et_obj < curr_time:
                prev_rows.append(r)
            elif earliest_future_slot and st_obj == earliest_future_slot:
                next_rows.append(r)
                
    def format_tracker_rows(label, rows_list):
        if not rows_list:
            return [{
                "Status": label,
                "Start_Time": "---",
                "Class": "---",
                "Section": "---",
                "Subject": "---"
            }]
        out = []
        for r in rows_list:
            display_label = label
            if r.get('Is_Sub', False):
                display_label += " (SUB)"
            out.append({
                "Status": display_label,
                "Start_Time": str(r.get('Start_Time', '')),
                "Class": str(r.get('Class', '')),
                "Section": str(r.get('Section', 'A')),
                "Subject": str(r.get('Subject', ''))
            })
        return out

    tracker_data = []
    tracker_data.extend(format_tracker_rows("⬅️ Previous", prev_rows))
    tracker_data.extend(format_tracker_rows("🟢 Current", curr_rows))
    tracker_data.extend(format_tracker_rows("➡️ Next", next_rows))
    
    tracker_df = pd.DataFrame(tracker_data)
    
    def highlight_current_row(row):
        if "Current" in str(row["Status"]):
            if "(SUB)" in str(row["Status"]):
                return ["background-color: #fff3cd; color: #856404; font-weight: bold"] * len(row)
            else:
                return ["background-color: #d4edda; color: #155724; font-weight: bold"] * len(row)
        else:
            return [""] * len(row)
            
    st.dataframe(
        tracker_df.style.apply(highlight_current_row, axis=1),
        hide_index=True,
        use_container_width=True
    )

# ==========================================
# 8. HOME PORTAL & NAVIGATION LOGIC
# ==========================================
app_page = st.Page("bps_digital.py", title="BPS Digital App", icon="🏫")
fees_page = st.Page("sch_exam_fees.py", title="Exam Fees", icon="💰")
udise_page = st.Page("UDISE+.py", title="UDISE+ Progression", icon="🎓")
gas_page = st.Page("bps_gas_tracker.py", title="Gas Tracker", icon="🛢️")
exam_page = st.Page("bps_exam.py", title="BPS Exams", icon="📝")
assembly_page = st.Page("bps_assembly.py", title="Assembly Planner", icon="🎙️") # <-- 1. Assembly Page Registered

def home_page_ui():
    st.markdown(f"<h3 style='margin-bottom: 5px;'>👋 Welcome, {st.session_state.user_name}</h3>", unsafe_allow_html=True)
    
    if st.session_state.user_role in ["teacher", "admin"]:
        render_tracker()
        
    st.markdown("#### 🚀 Select Application")
    
    # Primary Applications (Both Admin & Teachers)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏫 BPS Digital App", type="primary", use_container_width=True):
            st.switch_page(app_page)
    with col2:
        if st.button("📝 BPS Exams", type="primary", use_container_width=True):
            st.switch_page(exam_page)
            
    # Secondary Applications (Both Admin & Teachers)
    col3, col4 = st.columns(2)
    with col3:
        if st.button("💰 Funds & Fees", type="secondary", use_container_width=True):
            st.switch_page(fees_page)
            
    # ==========================================
    # ADMIN-ONLY APPLICATION BUTTONS
    # ==========================================
    if st.session_state.user_role == "admin":
        with col4:
            if st.button("🎙️ Assembly Planner", type="secondary", use_container_width=True): # <-- 2. Admin Assembly Button
                st.switch_page(assembly_page)
                
        col5, col6 = st.columns(2)
        with col5:
            if st.button("🎓 UDISE+ Progression", type="secondary", use_container_width=True):
                st.switch_page(udise_page)
        with col6:
            if st.button("🛢️ Gas Tracker", type="secondary", use_container_width=True):
                st.switch_page(gas_page)

home_page = st.Page(home_page_ui, title="Home Portal", icon="🏠", default=True)

nav_pages = {
    "Portal": [home_page],
    "Applications": [app_page, exam_page, fees_page]
}

# 3. Add Admin-Only pages to Sidebar Navigation
if st.session_state.user_role == "admin":
    nav_pages["Applications"].append(assembly_page) # <-- 3. Admin Sidebar Entry
    nav_pages["Applications"].append(udise_page)
    nav_pages["Applications"].append(gas_page)

pg = st.navigation(nav_pages)
pg.run()
