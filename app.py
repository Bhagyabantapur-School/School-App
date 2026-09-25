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
if 'user_id' not in st.session_state: st.session_state.user_id = None

# ==========================================
# 5. THE 'AUTO-LOGIN' CHECK (Survives Refreshes)
# ==========================================
if not st.session_state.authenticated:
    if "user" in st.query_params:
        url_user = st.query_params["user"]
        # Validate the user from the URL against our dictionary
        if url_user in USERS:
            st.session_state.authenticated = True
            st.session_state.user_role = USERS[url_user]["role"]
            st.session_state.user_name = USERS[url_user]["name"]
            st.session_state.user_id = url_user

# ==========================================
# 6. LOGIN SCREEN (GATEKEEPER)
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
                st.session_state.user_id = ui
                
                # Push the User ID to the URL to enable session survival on refresh
                st.query_params["user"] = ui
                
                st.rerun() 
            else: 
                st.error("❌ Incorrect Credentials")
    
    st.stop()

# ==========================================
# 7. SIDEBAR CONTROLS & MANUAL SYNC
# ==========================================
st.sidebar.success(f"👋 Welcome, {st.session_state.user_name}")

if st.sidebar.button("🔄 Sync Schedule", use_container_width=True, key="sync_routine_btn"):
    fetch_routine_data.clear()
    fetch_leave_data.clear()
    st.rerun()

if st.sidebar.button("Log Out", use_container_width=True): 
    st.query_params.clear()
    st.session_state.authenticated = False 
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.user_id = None
    st.rerun()
st.sidebar.markdown("---")

# ==========================================
# 8. LIVE ROUTINE TRACKER BANNER (CARD UI)
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
    
    is_fully_on_leave = False
    given_away_slots = []
    leave_type = ""
    
    if not ll.empty and 'Date' in ll.columns and 'Teacher' in ll.columns:
        user_leave = ll[(ll['Date'].astype(str).str.strip() == curr_date_str) & (ll['Teacher'].astype(str).str.strip() == st.session_state.user_name)]
        if not user_leave.empty:
            leave_type = str(user_leave.iloc[0].get('Type', 'Leave'))
            if leave_type in ['Class Shift / Internal Duty', 'Half Day']:
                given_away_slots = [a.split(": ")[0].strip() for a in str(user_leave.iloc[0].get('Detailed_Sub_Log', '')).split(" | ") if ": " in a and "None" not in a]
            else:
                is_fully_on_leave = True
            
    if is_fully_on_leave:
        st.warning(f"🏖️ You are marked on leave today ({leave_type}). Regular classes are hidden.")
        return

    ms = rout[(rout['Teacher'] == mc) & (rout['Day'] == tdy)].copy() if not rout.empty else pd.DataFrame()
    if not ms.empty:
        ms['Is_Sub'] = False
        if given_away_slots:
            ms = ms[~ms['Start_Time'].astype(str).str.strip().isin(given_away_slots)]
    
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
                
    # STRIcT SINGLE-LINE HTML GENERATOR TO PREVENT MARKDOWN ISSUES
    def generate_card_html(label, rows_list, css_class):
        if not rows_list:
            return f"<div class='tracker-card {css_class}'><div class='tc-label'>{label}</div><div class='tc-time'>---</div><div class='tc-details' style='color: #adb5bd;'>No Class Scheduled</div></div>"
        
        r = rows_list[0]
        sub_text = "<br><span style='font-size:12px; font-weight:bold; color:#d9534f;'>(SUBSTITUTION)</span>" if r.get('Is_Sub', False) else ""
        time_str = f"{r.get('Start_Time', '')} - {r.get('End_Time', '')}" if 'End_Time' in r else str(r.get('Start_Time', ''))
        details = f"Class {r.get('Class', '')} '{r.get('Section', 'A')}'<br><strong>{r.get('Subject', '')}</strong>{sub_text}"
        
        return f"<div class='tracker-card {css_class}'><div class='tc-label'>{label}</div><div class='tc-time'>{time_str}</div><div class='tc-details'>{details}</div></div>"

    # STRICT SINGLE-LINE CSS TO AVOID INDENTATION ERRORS
    css_string = "<style>.tracker-container { display: flex; gap: 15px; width: 100%; margin-bottom: 25px; flex-wrap: wrap; } .tracker-card { flex: 1 1 250px; padding: 15px 20px; border-radius: 12px; text-align: center; display: flex; flex-direction: column; justify-content: center; transition: transform 0.2s ease-in-out; } .tracker-card:hover { transform: translateY(-2px); } .tc-label { font-size: 13px; font-weight: 800; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.5px; } .tc-time { font-size: 22px; font-weight: 900; margin-bottom: 8px; font-family: monospace; } .tc-details { font-size: 15px; line-height: 1.5; } .card-past { background-color: #e2e3e5; color: #6c757d; border-left: 6px solid #adb5bd; box-shadow: inset 0 0 10px rgba(0,0,0,0.02); opacity: 0.85; } .card-current { background-color: #d4edda; color: #155724; border-left: 6px solid #28a745; border: 1px solid #c3e6cb; box-shadow: 0 4px 12px rgba(40, 167, 69, 0.15); } .card-future { background-color: #f8f9fa; color: #495057; border-left: 6px solid #0d6efd; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.03); }</style>"
    
    # CONSTRUCT FINAL HTML STRING ON ONE LINE
    html_content = css_string + f"<div class='tracker-container'>{generate_card_html('⬅️ Finished', prev_rows, 'card-past')}{generate_card_html('🟢 Ongoing Now', curr_rows, 'card-current')}{generate_card_html('➡️ Coming Up', next_rows, 'card-future')}</div>"
    
    st.markdown(html_content, unsafe_allow_html=True)

# ==========================================
# 9. HOME PORTAL & NAVIGATION LOGIC
# ==========================================
app_page = st.Page("bps_digital.py", title="BPS Digital App", icon="🏫")
fees_page = st.Page("sch_exam_fees.py", title="Exam Fees", icon="💰")
udise_page = st.Page("UDISE+.py", title="UDISE+ Progression", icon="🎓")
gas_page = st.Page("bps_gas_tracker.py", title="Gas Tracker", icon="🛢️")
exam_page = st.Page("bps_exam.py", title="BPS Exams", icon="📝")
assembly_page = st.Page("bps_assembly.py", title="Assembly Planner", icon="🎙️")
celeb_page = st.Page("bps_celebration.py", title="Celebrations", icon="🎊")
cookpro_page = st.Page("cookpro_tracker.py", title="CookPro Tracker", icon="👩‍🍳")

def home_page_ui():
    st.markdown(f"<h3 style='margin-bottom: 5px;'>👋 Welcome, {st.session_state.user_name}</h3>", unsafe_allow_html=True)
    
    if st.session_state.user_role in ["teacher", "admin"]:
        render_tracker()
        
    st.markdown("#### 🚀 Select Application")
    
    # Primary Applications
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏫 BPS Digital App", type="primary", use_container_width=True):
            st.switch_page(app_page)
    with col2:
        if st.button("📝 BPS Exams", type="primary", use_container_width=True):
            st.switch_page(exam_page)
            
    # Secondary Applications
    col3, col4 = st.columns(2)
    with col3:
        if st.button("💰 Funds & Fees", type="secondary", use_container_width=True):
            st.switch_page(fees_page)
    with col4:
        if st.button("🎊 Celebrations", type="secondary", use_container_width=True):
            st.switch_page(celeb_page)
            
    col7, col8 = st.columns(2)
    with col7:
        if st.button("👩‍🍳 CookPro Tracker", type="secondary", use_container_width=True):
            st.switch_page(cookpro_page)

    # Admin-only Applications
    if st.session_state.user_role == "admin":
        st.markdown("#### 🛠️ Admin Controls")
        col5, col6 = st.columns(2)
        with col5:
            if st.button("🎙️ Assembly Planner", type="secondary", use_container_width=True): 
                st.switch_page(assembly_page)
        with col6:
            if st.button("🎓 UDISE+ Progression", type="secondary", use_container_width=True):
                st.switch_page(udise_page)
                
        if st.button("🛢️ Gas Tracker", type="secondary", use_container_width=True):
            st.switch_page(gas_page)

home_page = st.Page(home_page_ui, title="Home Portal", icon="🏠", default=True)

nav_pages = {
    "Portal": [home_page],
    "Applications": [app_page, exam_page, celeb_page, fees_page, cookpro_page] 
}

if st.session_state.user_role == "admin":
    nav_pages["Applications"].append(assembly_page) 
    nav_pages["Applications"].append(udise_page)
    nav_pages["Applications"].append(gas_page)

pg = st.navigation(nav_pages)
pg.run()
