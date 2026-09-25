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

@st.cache_resource
def init_holiday_gsheet():
    try:
        return gspread.authorize(get_google_credentials()).open("MY ROUTINE 2026")
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

@st.cache_data(ttl=3600)
def fetch_holiday_data():
    try:
        h_sh = init_holiday_gsheet()
        if h_sh:
            ws = h_sh.worksheet("holidays")
            df = pd.DataFrame(ws.get_all_records()).infer_objects(copy=False)
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
    fetch_holiday_data.clear()
    st.rerun()

if st.sidebar.button("Log Out", use_container_width=True): 
    st.query_params.clear()
    st.session_state.authenticated = False 
    st.session_state.user_role = None
    st.session_state.user_name = None
    st.session_state.user_id = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; padding-top: 10px;">
    <span style="color: #6c757d; font-size: 12px;">Designed & Developed by</span><br>
    <span style="color: #00008B; font-size: 14px; font-weight: 700; letter-spacing: 0.5px;">Sukhamay Kisku</span>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 8. LIVE ROUTINE TRACKER BANNER
# ==========================================
def render_tracker():
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

    if not rout.empty:
        ms = rout[((rout['Teacher'] == mc) | (rout['Teacher'].astype(str).str.strip().str.upper() == 'ALL')) & (rout['Day'] == tdy)].copy()
    else:
        ms = pd.DataFrame()
        
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
    
    if not ms.empty:
        ms['Start_Obj'] = ms['Start_Time'].apply(parse_time_safe)
        ms['End_Obj'] = ms['End_Time'].apply(parse_time_safe)
        ms = ms.dropna(subset=['Start_Obj', 'End_Obj']).sort_values('Start_Obj')
        
        schedule_with_leisure = []
        ms_records = ms.to_dict('records')
        
        for i in range(len(ms_records)):
            curr_cls = ms_records[i]
            schedule_with_leisure.append(curr_cls)
            if i < len(ms_records) - 1:
                next_cls = ms_records[i+1]
                if curr_cls['End_Obj'] < next_cls['Start_Obj']:
                    leisure_cls = {
                        'Start_Time': curr_cls['End_Time'],
                        'End_Time': next_cls['Start_Time'],
                        'Start_Obj': curr_cls['End_Obj'],
                        'End_Obj': next_cls['Start_Obj'],
                        'Class': 'Leisure',
                        'Section': '-',
                        'Subject': '☕ Free Period',
                        'Teacher': mc,
                        'Is_Sub': False
                    }
                    schedule_with_leisure.append(leisure_cls)
                    
        ms = pd.DataFrame(schedule_with_leisure)
        
        def get_card_class(start_obj, end_obj):
            if end_obj < curr_time: return 'card-past'
            if start_obj <= curr_time <= end_obj: return 'card-current'
            return 'card-future'
            
        def generate_row_html(r, css_class):
            sub_text = "<span style='font-size:11px; font-weight:bold; color:#d9534f; margin-left:5px;'>(SUB)</span>" if r.get('Is_Sub', False) else ""
            time_str = str(r.get('Start_Time', ''))
            cls_str = f"{r.get('Class', '')} '{r.get('Section', 'A')}'"
            if str(r.get('Teacher', '')).strip().upper() == 'ALL':
                cls_str = f"{r.get('Class', 'Break')}"
            elif r.get('Class') == 'Leisure':
                cls_str = "Leisure Period"
            subj_str = f"<strong>{r.get('Subject', '')}</strong>{sub_text}"
            return f"<div class='tracker-card {css_class}'><div class='tc-time'>{time_str}</div><div class='tc-info'>{cls_str}</div><div class='tc-subj'>{subj_str}</div></div>"
            
        cards_html = ""
        for _, r in ms.iterrows():
            css_class = get_card_class(r['Start_Obj'], r['End_Obj'])
            cards_html += generate_row_html(r, css_class)
            
        css_string = "<style>.tracker-container { display: flex; flex-direction: column; gap: 4px; width: 100%; margin-bottom: 15px; } .tracker-card { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; border-radius: 8px; white-space: nowrap; overflow: hidden; } .tc-time { font-size: 15px; font-weight: 900; font-family: monospace; width: 20%; text-align: left; } .tc-info { font-size: 14px; font-weight: 600; width: 45%; text-align: center; overflow: hidden; text-overflow: ellipsis; } .tc-subj { font-size: 14px; width: 35%; text-align: right; overflow: hidden; text-overflow: ellipsis; } .card-past { background-color: #e2e3e5; color: #6c757d; border-left: 4px solid #adb5bd; opacity: 0.85; } .card-current { background-color: #d4edda; color: #155724; border-left: 4px solid #28a745; border: 1px solid #c3e6cb; box-shadow: 0 4px 12px rgba(40,167,69,0.15); } .card-future { background-color: #f8f9fa; color: #495057; border-left: 4px solid #0d6efd; border: 1px solid #e9ecef; }</style>"
        html_content = css_string + f"<div class='tracker-container'>{cards_html}</div>"
        st.markdown(html_content, unsafe_allow_html=True)
    else:
        st.info("No classes scheduled for you today.")

# ==========================================
# 8.5 UPCOMING HOLIDAY BANNER
# ==========================================
def render_upcoming_holiday():
    holidays_df = fetch_holiday_data()
    if not holidays_df.empty and 'Date' in holidays_df.columns and 'Occasion' in holidays_df.columns:
        utc_now = datetime.now(timezone.utc)
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        today = ist_now.date()
        
        holidays_df['ParsedDate'] = pd.to_datetime(holidays_df['Date'].astype(str).str.replace('.', '-').str.replace('/', '-'), format='%d-%m-%Y', errors='coerce')
        valid_holidays = holidays_df.dropna(subset=['ParsedDate']).sort_values('ParsedDate')
        
        upcoming = valid_holidays[valid_holidays['ParsedDate'].dt.date >= today]
        
        if not upcoming.empty:
            next_hol = upcoming.iloc[0]
            h_date = next_hol['ParsedDate'].date()
            h_occ = next_hol['Occasion']
            days_until = (h_date - today).days
            
            timing_str = "Today" if days_until == 0 else "Tomorrow" if days_until == 1 else f"in {days_until} days"
                
            st.markdown(f"""
            <div style='background-color: #f8f9fa; border-left: 4px solid #17a2b8; padding: 10px 15px; border-radius: 5px; margin-top: 5px;'>
                <span style='font-size: 13px; font-weight: 700; color: #495057; text-transform: uppercase; letter-spacing: 0.5px;'>🗓️ Upcoming Holiday</span><br>
                <span style='font-size: 15px; font-weight: 700; color: #17a2b8;'>{h_occ}</span> 
                <span style='font-size: 14px; color: #6c757d; font-weight: 500;'> • {h_date.strftime('%d %b %Y')} ({timing_str})</span>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# 8.6 DURGA PUJA WIDGET COUNTDOWN (PULSE EFFECT)
# ==========================================
def render_durga_puja_countdown():
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    today = ist_now.date()
    
    dp_start = datetime(2026, 10, 15).date()
    days_left = (dp_start - today).days
    
    if days_left > 0:
        css_string = "<style>@keyframes pulse-pink { 0% { box-shadow: 0 0 0 0 rgba(214,51,132,0.4); transform: scale(1); } 70% { box-shadow: 0 0 0 10px rgba(214,51,132,0); transform: scale(1.02); } 100% { box-shadow: 0 0 0 0 rgba(214,51,132,0); transform: scale(1); } } .puja-wrap { text-align: center; margin-bottom: 20px; margin-top: 5px; } .puja-widget { display: inline-flex; align-items: center; gap: 12px; background: linear-gradient(135deg, #fff0f3 0%, #ffe4e8 100%); border: 1px solid #ffc9d2; border-radius: 50px; padding: 6px 16px 6px 20px; animation: pulse-pink 2s infinite; box-shadow: 0 4px 12px rgba(214,51,132,0.15); } .puja-title { font-size: 13px; color: #d63384; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; margin: 0; } .puja-days { font-size: 16px; font-weight: 900; color: #b02a6b; background: rgba(255,255,255,0.7); padding: 4px 12px; border-radius: 30px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }</style>"
        html_content = css_string + f"<div class='puja-wrap'><div class='puja-widget'><span class='puja-title'>Durga Puja</span><span class='puja-days'>{days_left} DAYS</span></div></div>"
        st.markdown(html_content, unsafe_allow_html=True)
    elif days_left == 0:
        css_string = "<style>@keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(40,167,69,0.4); transform: scale(1); } 70% { box-shadow: 0 0 0 10px rgba(40,167,69,0); transform: scale(1.02); } 100% { box-shadow: 0 0 0 0 rgba(40,167,69,0); transform: scale(1); } } .puja-wrap { text-align: center; margin-bottom: 20px; margin-top: 5px; } .puja-widget-green { display: inline-flex; align-items: center; gap: 12px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 1px solid #bbf7d0; border-radius: 50px; padding: 6px 16px 6px 20px; animation: pulse-green 2s infinite; box-shadow: 0 4px 12px rgba(40,167,69,0.15); } .puja-title-green { font-size: 13px; color: #166534; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; margin: 0; } .puja-days-green { font-size: 16px; font-weight: 900; color: #15803d; background: rgba(255,255,255,0.7); padding: 4px 12px; border-radius: 30px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }</style>"
        html_content = css_string + f"<div class='puja-wrap'><div class='puja-widget-green'><span class='puja-title-green'>Durga Puja</span><span class='puja-days-green'>STARTS TODAY! 🎉</span></div></div>"
        st.markdown(html_content, unsafe_allow_html=True)

# ==========================================
# 9. HOME PORTAL & TABBED NAVIGATION LOGIC
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
    st.markdown(f"<h3 style='margin-bottom: 0px;'>👋 Welcome, {st.session_state.user_name}</h3>", unsafe_allow_html=True)
    
    # ⏳ Render Durga Puja Floating Pulse Widget
    render_durga_puja_countdown()
    
    # --- UI UPDATE: Creating Tabs ---
    tab1, tab2 = st.tabs(["📅 Today's Schedule", "🚀 Applications"])
    
    # --- TAB 1: Live Schedule Tracker ---
    with tab1:
        if st.session_state.user_role in ["teacher", "admin"]:
            render_tracker()
            render_upcoming_holiday()
        else:
            st.info("Schedules are only available for teachers and admins.")
            
    # --- TAB 2: Application Buttons ---
    with tab2:
        st.markdown("#### Select Application")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏫 BPS Digital App", type="primary", use_container_width=True):
                st.switch_page(app_page)
        with col2:
            if st.button("📝 BPS Exams", type="primary", use_container_width=True):
                st.switch_page(exam_page)
                
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
                
    # --- MAIN DASHBOARD FOOTER CREDIT ---
    st.markdown("""
    <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e9ecef; text-align: center;">
        <span style="color: #6c757d; font-size: 14px; font-weight: 500;">✨ Designed & Developed by </span>
        <span style="color: #00008B; font-size: 15px; font-weight: 700; letter-spacing: 0.5px;">Sukhamay Kisku</span>
    </div>
    """, unsafe_allow_html=True)

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
