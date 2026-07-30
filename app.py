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

@st.cache_data(ttl=120)
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

@st.cache_data(ttl=120)
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
# 6. SIDEBAR CONTROLS & AUTO-SYNC
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
# 7. LIVE ROUTINE TRACKER BANNER (HIDE IF ON LEAVE)
# ==========================================
def render_tracker():
    st.markdown("### ⏱️ My Live Class Tracker (Today's Schedule)")
    st.caption("Automatically syncs every 2 minutes with `bps_routine` and substitution plans in `BPS_Database`.")
    
    utc_now = datetime.now(timezone.utc)
    now = utc_now + timedelta(hours=5, minutes=30)
    curr_time = now.time()
    tdy = now.strftime('%A')
    curr_date_str = now.strftime('%d-%m-%Y')
    
    rout = fetch_routine_data()
    ll = fetch_leave_data()
    mc = TEACHER_INITIALS.get(st.session_state.user_name, st.session_state.user_name)
    
    # 1. Check if logged-in user is ON LEAVE today
    is_on_leave = False
    leave_type = ""
    if not ll.empty and 'Date' in ll.columns and 'Teacher' in ll.columns:
        user_leave = ll[(ll['Date'].astype(str).str.strip() == curr_date_str) & (ll['Teacher'].astype(str).str.strip() == st.session_state.user_name)]
        if not user_leave.empty:
            is_on_leave = True
            leave_type = str(user_leave.iloc[0].get('Type', 'Leave'))
            
    if is_on_leave:
        st.warning(f"🏖️ You are marked on leave today ({leave_type}). Regular classes are hidden.")
        ms = pd.DataFrame()  # Wipe out classes if on leave
    else:
        # 2. Get Default Regular Schedule
        ms = rout[(rout['Teacher'] == mc) & (rout['Day'] == tdy)].copy() if not rout.empty else pd.DataFrame()
        if not ms.empty:
            ms['Is_Sub'] = False
        
        # 3. Check and Merge Today's Substitution Assignments from teacher_leave
        sd = []
        if not ll.empty and 'Date' in ll.columns and not rout.empty:
            for _, r in ll[ll['Date'].astype(str).str.strip() == curr_date_str].iterrows():
                sub_log = str(r.get('Detailed_Sub_Log', ''))
                if st.session_state.user_name in sub_log:
                    absent_teacher = str(r.get('Teacher', '')).strip()
                    absent_initials = TEACHER_INITIALS.get(absent_teacher, absent_teacher)
                    
                    for item in sub_log.split(" | "):
                        if f": {st.session_state.user_name}" in item:
                            slot = item.split(": ")[0].strip()
                            oc = rout[(rout['Teacher'] == absent_initials) & (rout['Day'] == tdy) & (rout['Start_Time'].astype(str).str.strip() == slot)]
                            if not oc.empty:
                                rx = oc.iloc[0]
                                sd.append({
                                    'Start_Time': rx['Start_Time'],
                                    'End_Time': rx['End_Time'],
                                    'Class': rx['Class'],
                                    'Section': rx.get('Section', 'A'),
                                    'Subject': f"🔄 {rx['Subject']} (Sub for {absent_teacher})",
                                    'Teacher': mc,
                                    'Day': tdy,
                                    'Is_Sub': True
                                })
        
        if sd:
            ms = pd.concat([ms, pd.DataFrame(sd)], ignore_index=True)
    
    prev_row, curr_row, next_row = None, None, None
    
    if not ms.empty:
        ms['Start_Obj'] = ms['Start_Time'].apply(parse_time_safe)
        ms['End_Obj'] = ms['End_Time'].apply(parse_time_safe)
        ms = ms.dropna(subset=['Start_Obj', 'End_Obj']).sort_values('Start_Obj')
        
        for _, r in ms.iterrows():
            st_obj = r['Start_Obj']
            et_obj = r['End_Obj']
            if et_obj < curr_time:
                prev_row = r  # Most recently completed class
            elif st_obj <= curr_time <= et_obj:
                curr_row = r  # Ongoing active class
            elif st_obj > curr_time:
                if next_row is None:
                    next_row = r  # First upcoming class
                    
    def format_tracker_row(label, row_data):
        if row_data is not None:
            return {
                "Status": label,
                "Start_Time": str(row_data.get('Start_Time', '')),
                "Class": str(row_data.get('Class', '')),
                "Section": str(row_data.get('Section', 'A')),
                "Subject": str(row_data.get('Subject', ''))
            }
        else:
            return {
                "Status": label,
                "Start_Time": "---",
                "Class": "---",
                "Section": "---",
                "Subject": "---"
            }

    tracker_df = pd.DataFrame([
        format_tracker_row("⬅️ Previous", prev_row),
        format_tracker_row("🟢 Current", curr_row),
        format_tracker_row("➡️ Next", next_row)
    ])
    
    # Highlight Current Class row in light green
    def highlight_current_row(row):
        if "Current" in str(row["Status"]):
            return ["background-color: #d4edda; color: #155724; font-weight: bold"] * len(row)
        else:
            return [""] * len(row)
            
    st.dataframe(
        tracker_df.style.apply(highlight_current_row, axis=1),
        hide_index=True,
        use_container_width=True
    )
    
    # 2-Minute (120,000 ms) Auto-Refresh script
    components.html("""
        <script>
            setTimeout(function() {
                const buttons = window.parent.document.querySelectorAll('button');
                buttons.forEach(btn => {
                    if (btn.innerText.includes('Sync Schedule')) {
                        btn.click();
                    }
                });
            }, 120000);
        </script>
    """, height=0, width=0)
    
    st.divider()

# ==========================================
# 8. HOME PORTAL & NAVIGATION LOGIC
# ==========================================
app_page = st.Page("bps_digital.py", title="BPS Digital App", icon="🏫")
fees_page = st.Page("sch_exam_fees.py", title="Exam Fees", icon="💰")
udise_page = st.Page("UDISE+.py", title="UDISE+ Progression", icon="🎓")
gas_page = st.Page("bps_gas_tracker.py", title="Gas Tracker", icon="🛢️")

def home_page_ui():
    # Show banner for BOTH Teacher and Admin logins
    if st.session_state.user_role in ["teacher", "admin"]:
        render_tracker()
        
    st.markdown(f"<h2 style='text-align: center;'>Welcome to the Unified Hub, {st.session_state.user_name}!</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Select an application from the sidebar or click below to launch your primary workspace.</p>", unsafe_allow_html=True)
    
    st.write("")
    st.write("")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Enter BPS Digital App", type="primary", use_container_width=True):
            st.switch_page(app_page)
            
        st.write("")
        
        if st.button("💰 Enter Funds & Fees", type="secondary", use_container_width=True):
            st.switch_page(fees_page)
            
        if st.session_state.user_role == "admin":
            st.write("")
            if st.button("🎓 Enter UDISE+ Progression", type="secondary", use_container_width=True):
                st.switch_page(udise_page)
            st.write("")
            if st.button("🛢️ Enter Gas Tracker", type="secondary", use_container_width=True):
                st.switch_page(gas_page)

home_page = st.Page(home_page_ui, title="Home Portal", icon="🏠", default=True)

nav_pages = {
    "Portal": [home_page],
    "Applications": [app_page, fees_page]
}

if st.session_state.user_role == "admin":
    nav_pages["Applications"].append(udise_page)
    nav_pages["Applications"].append(gas_page)

pg = st.navigation(nav_pages)
pg.run()
