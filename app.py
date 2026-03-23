import streamlit as st
import pandas as pd
import os
import calendar
import base64
import re
import concurrent.futures
from datetime import datetime, time, timedelta, timezone
from streamlit_qrcode_scanner import qrcode_scanner
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Digital", page_icon="🏫", layout="centered")

def inject_security_css(user_name):
    watermark_text = f"{user_name} - CONFIDENTIAL"
    st.markdown(f"""
    <style>
        body {{ user-select: none; -webkit-user-select: none; -ms-user-select: none; }}
        .watermark {{
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            pointer-events: none; z-index: 9999;
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><text x="50" y="150" fill="rgba(200, 200, 200, 0.25)" font-size="20" transform="rotate(-45 150 150)" font-family="Arial, sans-serif">{watermark_text}</text></svg>');
            background-repeat: repeat;
        }}
        #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} header {{visibility: hidden;}}
        [data-testid="stSidebar"] {{display: none;}}
        .block-container {{ padding-top: 1rem; max-width: 650px; overflow-x: hidden; }}
        .school-title {{ font-size: 26px !important; font-weight: 900 !important; color: #1a1a1a; margin: 0; line-height: 1.1; }}
        .bps-subtext {{ font-size: 14px; font-weight: 800; color: #007bff; margin-top: -5px; letter-spacing: 1px; }}
        .summary-card {{ background-color: #ffffff; border: 2px solid #007bff; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); }}
        .stButton>button {{ width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; border: none; }}
        .routine-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #007bff; margin-bottom: 15px; border-right: 1px solid #ddd; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; }}
        .login-box {{ padding: 20px; border-radius: 15px; background-color: #f0f2f6; border: 1px solid #d1d5db; margin-top: 20px; }}
        .report-table {{ width: 100%; border-collapse: collapse; }}
        .report-table td, .report-table th {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
        .report-table th {{ background-color: #007bff; color: white; }}
        .att-badge {{ padding: 8px 12px; border-radius: 8px; font-weight: bold; font-size: 15px; display: block; text-align: center; margin-top: 5px; margin-bottom: 5px;}}
        .att-wait {{ background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }}
        .att-done {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .att-neutral {{ background-color: #e2e6ea; color: #333; border: 1px solid #ccc; }}
        .sub-card {{ background-color: #e3f2fd; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 4px solid #2196f3; }}
        .sub-row {{ background-color: #fff3cd !important; border-left: 5px solid #ffc107 !important; }}
        
        /* 📱 AGGRESSIVE MOBILE LAYOUT LOCK */
        @media (max-width: 768px) {{
            .roster-container [data-testid="stHorizontalBlock"] {{
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                align-items: center !important;
                width: 100% !important;
            }}
            .roster-container [data-testid="column"] {{
                display: block !important;
                min-width: 0 !important; 
                margin-top: 0 !important;
                padding: 0 4px !important;
            }}
            /* Photo Column: Force to 55px */
            .roster-container [data-testid="column"]:nth-child(1) {{ 
                flex: 0 0 55px !important; 
                max-width: 55px !important; 
                width: 55px !important;
            }}
            /* Text Column: Take all remaining space */
            .roster-container [data-testid="column"]:nth-child(2) {{ 
                flex: 1 1 0% !important; 
                max-width: calc(100% - 150px) !important; 
                width: auto !important;
            }}
            /* Checkbox Column: Force to 95px */
            .roster-container [data-testid="column"]:nth-child(3) {{ 
                flex: 0 0 95px !important; 
                max-width: 95px !important; 
                width: 95px !important;
            }}
            
            /* Text Wrapping and Tightening */
            .roster-container .stCheckbox p {{ font-size: 13px !important; padding-left: 1.2rem !important; margin-bottom: 0px !important; line-height: 1.2 !important; }}
            .roster-container .stCheckbox {{ min-height: 1.2rem; }}
        }}
    </style>
    <script>document.addEventListener('contextmenu', event => event.preventDefault());</script>
    <div class="watermark"></div>
    """, unsafe_allow_html=True)

# --- 2. USER DATABASE ---
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

TEACHER_INITIALS = {"SUKHAMAY KISKU": "SK", "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS", "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP", "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"}
INV_TEACHER_INITIALS = {v: k for k, v in TEACHER_INITIALS.items()}
TEACHER_LIST = [u["name"] for k, u in USERS.items()]
CLASS_OPTIONS = ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
ATTENDANCE_OPTIONS = ["Select Class...", "CLASS PP A", "CLASS I A", "CLASS II A", "CLASS III A", "CLASS IV A", "CLASS IV B", "CLASS V A"]

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_role' not in st.session_state: st.session_state.user_role = None
if 'user_name' not in st.session_state: st.session_state.user_name = None

# --- 3. GOOGLE SHEETS CONNECTION & DATABASE ENGINE ---
@st.cache_resource
def get_google_credentials():
    skey = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    return Credentials.from_service_account_info(skey, scopes=scopes)

@st.cache_resource
def init_gsheets():
    try:
        creds = get_google_credentials()
        gc = gspread.authorize(creds)
        return gc.open("BPS_Database")
    except Exception as e:
        st.error("⚠️ Google Sheets Connection Failed! Please check your Streamlit Secrets.")
        st.stop()

@st.cache_resource
def get_drive_session():
    creds = get_google_credentials()
    return AuthorizedSession(creds)

sh = init_gsheets()

@st.cache_data(ttl=5) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        # Updated to comply with Pandas 2026 standards
        df = df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
        return df
    except:
        return pd.DataFrame()

def clear_sheet_cache():
    fetch_sheet_data.clear()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: 
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    except Exception as e:
        st.error("⚠️ Google Sheets API is busy (Rate Limit). Please wait 30 seconds and try again.")
        return
    
    df = df.fillna("").astype(str)
    try:
        ws.append_rows(df.values.tolist())
        clear_sheet_cache()
    except Exception as e:
        st.error("⚠️ Google Sheets API is busy. Please try submitting again in a moment.")

def overwrite_sheet_df(sheet_name, df):
    try: 
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
    except Exception as e:
        st.error("⚠️ Google Sheets API is busy (Rate Limit). Please wait 30 seconds and try again.")
        return
        
    try:
        ws.clear()
        df = df.fillna("").astype(str)
        if not df.empty:
            ws.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1')
        clear_sheet_cache()
    except Exception as e:
        st.error("⚠️ Google Sheets API is busy. Please try submitting again in a moment.")

def get_notice():
    try: return sh.worksheet("notice").acell("A1").value or ""
    except: return ""

def publish_notice(text):
    try: ws = sh.worksheet("notice")
    except: ws = sh.add_worksheet(title="notice", rows=10, cols=10)
    ws.update_acell("A1", text)

def get_local_csv(file):
    if os.path.exists(file): 
        try: return pd.read_csv(file)
        except: return pd.DataFrame()
    return pd.DataFrame()

# --- 4. SECURE IMAGE FETCHING (Thumbnails) ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        authed_session = get_drive_session()
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        response = authed_session.get(url)
        if response.status_code == 200:
            return response.content
        return None
    except Exception:
        return None

def get_secure_photo_uri(url):
    fallback_image = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str):
        return fallback_image

    file_id = None
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match: file_id = match.group(1)

    if file_id:
        image_bytes = fetch_secure_image_bytes(file_id)
        if image_bytes:
            b64_str = base64.b64encode(image_bytes).decode()
            return f"data:image/jpeg;base64,{b64_str}"
            
    return url if url.startswith("http") else fallback_image


# --- 5. TIME HELPERS ---
utc_now = datetime.now(timezone.utc)
now = utc_now + timedelta(hours=5, minutes=30)
curr_date_str = now.strftime("%d-%m-%Y")
curr_time = now.time()

def parse_time_safe(t_str):
    t_str = str(t_str).strip()
    for fmt in ('%H:%M', '%I:%M %p', '%H:%M:%S'):
        try: return datetime.strptime(t_str, fmt).time()
        except: continue
    return None

# ==========================================
# LOGIN SCREEN
# ==========================================
if not st.session_state.authenticated:
    inject_security_css("BPS DIGITAL") 
    
    public_notice = get_notice()
    if public_notice.strip(): st.info(f"📢 NOTICE: {public_notice}")

    st.markdown("<div class='login-box'><h3>🔐 Staff Login</h3><p>Please enter your Username & Password.</p></div>", unsafe_allow_html=True)
    with st.form("login_form"):
        username_input = st.text_input("Username (e.g., tr, admin)", key="ui").lower().strip()
        password_input = st.text_input("Password", type="password", key="pi")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if username_input in USERS:
                user_data = USERS[username_input]
                if password_input == user_data["password"]:
                    st.session_state.authenticated = True
                    st.session_state.user_role = user_data["role"]
                    st.session_state.user_name = user_data["name"]
                    st.rerun()
                else: st.error("❌ Incorrect Password")
            else: st.error("❌ Username not found")
    
    with st.expander("📅 View Holiday List (Public)"):
        h_df = get_local_csv('holidays.csv')
        if not h_df.empty: st.table(h_df)
        else: st.info("No data.")

else:
    inject_security_css(st.session_state.user_name)
    st.success(f"👋 Welcome, {st.session_state.user_name}")
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

    # ==========================================
    # ASSISTANT TEACHER DASHBOARD
    # ==========================================
    if st.session_state.user_role == "teacher":
        t_name_select = st.session_state.user_name
        h_df = get_local_csv('holidays.csv')
        is_h = not h_df[h_df['Date'] == curr_date_str].empty if not h_df.empty else False
        
        if is_h or now.strftime('%A') == 'Sunday':
            st.warning("🏖️ School is closed today.")
        else:
            n_text = get_notice()
            if n_text.strip(): st.info(f"📢 NOTICE: {n_text}")
            
            at_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leave Status", "🎓 Students Notice", "📅 Holidays"])

            # --- TAB 1: MDM ENTRY ---
            with at_tabs[0]: 
                mdm_log = fetch_sheet_data('mdm_log')
                already_sub = False
                
                if not mdm_log.empty and 'Date' in mdm_log.columns and 'Teacher' in mdm_log.columns:
                    mdm_log['Date'] = mdm_log['Date'].astype(str).str.strip()
                    mdm_log['Teacher'] = mdm_log['Teacher'].astype(str).str.strip()
                    if not mdm_log[(mdm_log['Date'] == curr_date_str) & (mdm_log['Teacher'] == t_name_select)].empty:
                        already_sub = True

                if already_sub: 
                    st.success("✅ MDM Submitted for today.")
                else:
                    st.subheader("Student MDM Entry")
                    
                    routine = get_local_csv('routine.csv')
                    my_code = TEACHER_INITIALS.get(t_name_select, t_name_select)
                    today_day = now.strftime('%A')
                    
                    target_class, target_section = None, None
                    is_substituting, absent_teacher_name = False, ""

                    leave_log = fetch_sheet_data('teacher_leave')
                    if not leave_log.empty and 'Date' in leave_log.columns:
                        today_leaves = leave_log[leave_log['Date'] == curr_date_str]
                        for _, row in today_leaves.iterrows():
                            log = str(row.get('Detailed_Sub_Log', ''))
                            if f"11:15: {t_name_select}" in log or f"11:15 AM: {t_name_select}" in log:
                                is_substituting = True
                                absent_teacher_name = row['Teacher']
                                absent_code = TEACHER_INITIALS.get(absent_teacher_name, "")
                                
                                absent_routine = routine[(routine['Teacher'] == absent_code) & (routine['Day'] == today_day)].copy()
                                absent_routine['Start_Obj'] = absent_routine['Start_Time'].apply(parse_time_safe)
                                match = absent_routine[absent_routine['Start_Obj'] == time(11, 15)]
                                
                                if not match.empty:
                                    target_class, target_section = match.iloc[0]['Class'], match.iloc[0].get('Section', 'A')
                                break
                    
                    if not target_class:
                        my_sched = routine[(routine['Teacher'] == my_code) & (routine['Day'] == today_day)].copy() if not routine.empty else pd.DataFrame()
                        if not my_sched.empty:
                            my_sched['Start_Obj'] = my_sched['Start_Time'].apply(parse_time_safe)
                            target_rows = my_sched[my_sched['Start_Obj'] == time(11, 15)]
                            if not target_rows.empty:
                                target_class, target_section = target_rows.iloc[0]['Class'], target_rows.iloc[0].get('Section', 'A')

                    if target_class:
                        if is_substituting: st.info(f"🔄 **SUBSTITUTION:** Covering for **{absent_teacher_name}** ({target_class} - {target_section})")
                        else: st.info(f"📌 Assigned **11:15 AM** class: **{target_class} - {target_section}**")
                        
                        students = fetch_sheet_data('students_master')

                        if not students.empty:
                            if 'Section' not in students.columns: students['Section'] = 'A'
                            roster = students[(students['Class'] == target_class) & (students['Section'] == target_section)].copy()
                            
                            if not roster.empty:
                                if 'scanned_keys' not in st.session_state: st.session_state.scanned_keys = []

                                st.write("📸 **Scan ID Cards (or tick manually below):**")
                                qr_val = qrcode_scanner(key='at_qr')
                                
                                if qr_val:
                                    try:
                                        parts = qr_val.split('|')
                                        qr_dict = {p.split(':')[0].strip(): p.split(':')[1].strip() for p in parts if ':' in p}
                                        s_roll, s_name = str(qr_dict.get('Roll', '')), str(qr_dict.get('Name', ''))
                                        
                                        if s_roll and s_name:
                                            is_valid_student = not roster[(roster['Roll'].astype(str) == s_roll) & (roster['Name'].astype(str) == s_name)].empty
                                            if is_valid_student:
                                                scan_key = f"{s_roll}_{s_name}"
                                                if scan_key not in st.session_state.scanned_keys:
                                                    st.session_state.scanned_keys.append(scan_key)
                                                    st.success(f"✅ Scanned: {s_name}")
                                            else: st.error(f"❌ MISMATCH: {s_name} is NOT in {target_class} {target_section}!")
                                    except: st.warning("⚠️ Invalid ID Card.")

                                roster['Scan_Key'] = roster['Roll'].astype(str) + "_" + roster['Name'].
