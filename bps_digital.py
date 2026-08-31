import streamlit as st, streamlit.components.v1 as components, pandas as pd, os, calendar, base64, re, concurrent.futures
from datetime import datetime, time, timedelta, timezone
from streamlit_qrcode_scanner import qrcode_scanner
import gspread
from gspread.exceptions import WorksheetNotFound, SpreadsheetNotFound
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

# If accessed directly without logging in via app.py, block execution
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

# Re-initialize states strictly used by bps_digital.py
if 'scan_msg' not in st.session_state: st.session_state.scan_msg = None
if 'scanned_keys' not in st.session_state: st.session_state.scanned_keys = []
if 'admin_scanned_keys' not in st.session_state: st.session_state.admin_scanned_keys = []
if 'admin_scan_msg' not in st.session_state: st.session_state.admin_scan_msg = None

# Callbacks to protect Checkbox memory from Streamlit refreshes
def t_toggle(k):
    if st.session_state[k]:
        if k not in st.session_state.scanned_keys: st.session_state.scanned_keys.append(k)
    else:
        if k in st.session_state.scanned_keys: st.session_state.scanned_keys.remove(k)

def a_toggle(k):
    if st.session_state[k]:
        if k not in st.session_state.admin_scanned_keys: st.session_state.admin_scanned_keys.append(k)
    else:
        if k in st.session_state.admin_scanned_keys: st.session_state.admin_scanned_keys.remove(k)

TEACHER_INITIALS = {"SUKHAMAY KISKU": "SK", "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS", "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP", "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"}
INV_TEACHER_INITIALS = {v: k for k, v in TEACHER_INITIALS.items()}
TEACHER_LIST = list(TEACHER_INITIALS.keys())
CLASS_OPTIONS = ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
ATTENDANCE_OPTIONS = ["Select Class...", "CLASS PP A", "CLASS I A", "CLASS II A", "CLASS III A", "CLASS IV A", "CLASS IV B", "CLASS V A"]

def inject_beep_script():
    js = (
        "<script>"
        "const doc = window.parent.document;"
        "if (!doc.getElementById('beep-listener-setup')) {"
        "doc.body.insertAdjacentHTML('beforeend', '<div id=\"beep-listener-setup\" style=\"display:none;\"></div>');"
        "doc.body.addEventListener('change', function(e) {"
        "if (e.target && e.target.type === 'checkbox') {"
        "const AudioContext = window.parent.AudioContext || window.parent.webkitAudioContext;"
        "if (AudioContext) {"
        "const ctx = new AudioContext();"
        "const osc = ctx.createOscillator(), gainNode = ctx.createGain();"
        "osc.type = 'sine'; osc.frequency.setValueAtTime(880, ctx.currentTime);"
        "gainNode.gain.setValueAtTime(0.1, ctx.currentTime);"
        "gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1);"
        "osc.connect(gainNode); gainNode.connect(ctx.destination);"
        "osc.start(); osc.stop(ctx.currentTime + 0.1);"
        "}}});}"
        "</script>"
    )
    components.html(js, height=0, width=0)

inject_beep_script()

def inject_security_css(user_name):
    wm = str(user_name) + " - CONFIDENTIAL"
    css = (
        "<style>"
        "body { user-select: none; -webkit-user-select: none; }"
        ".watermark { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 9999; "
        "background-image: url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"300\" height=\"300\" viewBox=\"0 0 300 300\">"
        "<text x=\"50\" y=\"150\" fill=\"rgba(200, 200, 200, 0.25)\" font-size=\"20\" transform=\"rotate(-45 150 150)\" font-family=\"Arial, sans-serif\">" + wm + "</text></svg>'); "
        "background-repeat: repeat; }"
        ".block-container { padding-top: 1rem; max-width: 800px; overflow-x: hidden; }"
        ".summary-card { background-color: #fff; border: 2px solid #007bff; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); }"
        ".stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; border: none; }"
        ".routine-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #007bff; margin-bottom: 15px; border-right: 1px solid #ddd; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; display: flex; flex-direction: column; gap: 4px;}"
        ".report-table { width: 100%; border-collapse: collapse; } .report-table td, .report-table th { border: 1px solid #ddd; padding: 8px; text-align: center; } .report-table th { background-color: #007bff; color: white; }"
        ".att-badge { padding: 8px 12px; border-radius: 8px; font-weight: bold; font-size: 15px; display: block; text-align: center; margin-top: 5px; margin-bottom: 5px;}"
        ".att-wait { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; } .att-done { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }"
        ".floating-counter { position: fixed; top: 15px; right: 15px; background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 10px 20px; border-radius: 30px; z-index: 999999; font-size: 16px; font-weight: 900; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); border: 2px solid #ffffff; pointer-events: none; transition: all 0.3s ease; }"
        "@media (max-width: 768px) {"
        ".floating-counter { top: 10px; right: 10px; font-size: 14px; padding: 8px 16px; }"
        ".roster-container [data-testid=\"stHorizontalBlock\"] { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; width: 100% !important; }"
        ".roster-container [data-testid=\"column\"] { display: block !important; min-width: 0 !important; margin-top: 0 !important; padding: 0 4px !important; }"
        ".roster-container [data-testid=\"column\"]:nth-child(1) { flex: 0 0 55px !important; max-width: 55px !important; width: 55px !important; }"
        ".roster-container [data-testid=\"column\"]:nth-child(2) { flex: 1 1 0% !important; max-width: calc(100% - 150px) !important; width: auto !important; }"
        ".roster-container [data-testid=\"column\"]:nth-child(3) { flex: 0 0 95px !important; max-width: 95px !important; width: 95px !important; }"
        ".roster-container .stCheckbox p { font-size: 13px !important; padding-left: 1.2rem !important; margin-bottom: 0px !important; line-height: 1.2 !important; }"
        ".roster-container .stCheckbox { min-height: 1.2rem; }"
        ".header-school-name { font-size: 18px !important; }"
        "}"
        "</style><script>document.addEventListener('contextmenu', e => e.preventDefault());</script><div class=\"watermark\"></div>"
    )
    st.markdown(css, unsafe_allow_html=True)

@st.cache_resource
def get_google_credentials(): return Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"])

@st.cache_resource
def init_gsheets():
    try: return gspread.authorize(get_google_credentials()).open("BPS_Database")
    except Exception: st.error("⚠️ Google Sheets Connection Failed!"); st.stop()

@st.cache_resource
def init_routine_gsheet():
    try: return gspread.authorize(get_google_credentials()).open("bps_routine")
    except Exception: return None

@st.cache_resource
def get_drive_session(): return AuthorizedSession(get_google_credentials())

sh = init_gsheets()

@st.cache_data(ttl=600) 
def fetch_sheet_data(sheet_name):
    try: return pd.DataFrame(sh.worksheet(sheet_name).get_all_records()).replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
    except Exception: return pd.DataFrame()

# ==========================================
# SYSTEM SETTINGS ENGINE
# ==========================================
def get_mdm_threshold():
    df = fetch_sheet_data('settings')
    if not df.empty and 'Key' in df.columns:
        m = df[df['Key'] == 'MDM_REGULAR_THRESHOLD']
        if not m.empty: return str(m.iloc[0]['Value'])
    return "1"

def set_setting(key, value):
    try: ws = sh.worksheet("settings")
    except Exception: ws = sh.add_worksheet(title="settings", rows=10, cols=2); ws.append_row(["Key", "Value"])
    df = fetch_sheet_data('settings')
    if df.empty or 'Key' not in df.columns: df = pd.DataFrame([{"Key": key, "Value": value}])
    else:
        if key in df['Key'].values: df.loc[df['Key'] == key, 'Value'] = value
        else: df = pd.concat([df, pd.DataFrame([{"Key": key, "Value": value}])], ignore_index=True)
    overwrite_sheet_df('settings', df)

# ==========================================
# BPS EXAM ROUTINE ENGINE
# ==========================================
@st.cache_data(ttl=300)
def fetch_exam_schedules():
    try:
        sh_ex = gspread.authorize(get_google_credentials()).open("BPS EXAM")
        ws = sh_ex.worksheet("schedules")
        df = pd.DataFrame(ws.get_all_records()).astype(str)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()

def build_exam_day_routine(date_str):
    schedules = fetch_exam_schedules()
    if schedules.empty or 'Date' not in schedules.columns:
        return pd.DataFrame()
        
    today_exams = schedules[schedules['Date'].astype(str).str.strip() == date_str]
    if today_exams.empty:
        return pd.DataFrame()
        
    all_dates = schedules['Date'].unique().tolist()
    date_objs = []
    for d in all_dates:
        try: date_objs.append(datetime.strptime(str(d).strip(), "%d-%m-%Y"))
        except Exception: pass
    date_objs.sort()
    
    curr_obj = datetime.strptime(date_str, "%d-%m-%Y")
    next_obj = None
    for d_obj in date_objs:
        if d_obj > curr_obj:
            next_obj = d_obj
            break
            
    next_date_str = next_obj.strftime("%d-%m-%Y") if next_obj else None
    next_exams = schedules[schedules['Date'].astype(str).str.strip() == next_date_str] if next_date_str else pd.DataFrame()
    
    routine_rows = []
    tdy_name = datetime.strptime(date_str, "%d-%m-%Y").strftime("%A")
    
    for _, row in today_exams.iterrows():
        c = str(row.get('Class', ''))
        sec = str(row.get('Section', 'A'))
        sub = str(row.get('Subject', ''))
        teacher_name = str(row.get('Teacher', ''))
        t_init = TEACHER_INITIALS.get(teacher_name, teacher_name)
        
        routine_rows.append({
            "Day": tdy_name,
            "Start_Time": "11:15",
            "End_Time": "12:45",
            "Class": c,
            "Section": sec,
            "Subject": f"📝 EXAM: {sub}",
            "Teacher": t_init,
            "Is_Custom": True,
            "Is_Exam_Day": True
        })
        
        next_sub = "📖 Final Revision"
        next_t_init = t_init
        if not next_exams.empty:
            match_next = next_exams[(next_exams['Class'] == c) & (next_exams['Section'] == sec)]
            if not match_next.empty:
                next_sub_val = str(match_next.iloc[0]['Subject'])
                next_teacher_val = str(match_next.iloc[0]['Teacher'])
                next_sub = f"📖 Prep: {next_sub_val} (Next Exam)"
                next_t_init = TEACHER_INITIALS.get(next_teacher_val, next_teacher_val)
            else:
                next_sub = "📖 Study / Exam Prep"
                
        routine_rows.append({
            "Day": tdy_name,
            "Start_Time": "12:45",
            "End_Time": "13:30",
            "Class": c,
            "Section": sec,
            "Subject": next_sub,
            "Teacher": next_t_init,
            "Is_Custom": True,
            "Is_Exam_Day": True
        })
        
        routine_rows.append({
            "Day": tdy_name,
            "Start_Time": "14:20",
            "End_Time": "15:30",
            "Class": c,
            "Section": sec,
            "Subject": f"✍️ Exam Copies Check ({sub})",
            "Teacher": t_init,
            "Is_Custom": True,
            "Is_Exam_Day": True
        })
        
    return pd.DataFrame(routine_rows)

@st.cache_data(ttl=600)
def fetch_all_routines():
    try:
        r_sh = init_routine_gsheet()
        if r_sh:
            df_base = pd.DataFrame(r_sh.worksheet("Sheet1").get_all_records()).astype(str)
            df_base.columns = [str(c).strip() for c in df_base.columns]
            try: 
                df_override = pd.DataFrame(r_sh.worksheet("daily_override").get_all_records()).astype(str)
                df_override.columns = [str(c).strip() for c in df_override.columns]
            except Exception: 
                df_override = pd.DataFrame()
            return df_base, df_override
    except Exception: pass
    return pd.DataFrame(), pd.DataFrame()

def get_active_routine(date_str, day_of_week):
    exam_routine = build_exam_day_routine(date_str)
    if not exam_routine.empty:
        return exam_routine
        
    base, override = fetch_all_routines()
    if not override.empty and 'Date' in override.columns:
        day_ov = override[override['Date'] == date_str].copy()
        if not day_ov.empty:
            day_ov['Is_Custom'] = True
            day_ov['Is_Exam_Day'] = False
            return day_ov
    
    if not base.empty and 'Day' in base.columns:
        day_base = base[base['Day'] == day_of_week].copy()
        day_base['Is_Custom'] = False
        day_base['Is_Exam_Day'] = False
        return day_base
        
    return pd.DataFrame()

def save_daily_routine(date_str, edited_df):
    r_sh = init_routine_gsheet()
    if not r_sh: return
    try: ws = r_sh.worksheet("daily_override")
    except WorksheetNotFound: 
        ws = r_sh.add_worksheet(title="daily_override", rows=1000, cols=10)
        ws.append_row(["Date", "Start_Time", "End_Time", "Class", "Section", "Subject", "Teacher"])
        
    records = ws.get_all_records()
    existing = pd.DataFrame(records)
    if not existing.empty and 'Date' in existing.columns:
        existing = existing[existing['Date'].astype(str) != date_str]
        
    edited_df['Date'] = date_str
    cols = ["Date", "Start_Time", "End_Time", "Class", "Section", "Subject", "Teacher"]
    for c in cols:
        if c not in edited_df.columns: edited_df[c] = ""
            
    edited_df = edited_df[cols]
    final_df = pd.concat([existing, edited_df], ignore_index=True) if not existing.empty else edited_df
    ws.clear()
    ws.update([final_df.columns.values.tolist()] + final_df.fillna("").values.tolist())
    fetch_all_routines.clear()

def delete_daily_routine(date_str):
    r_sh = init_routine_gsheet()
    if not r_sh: return
    try: ws = r_sh.worksheet("daily_override")
    except WorksheetNotFound: return
        
    records = ws.get_all_records()
    existing = pd.DataFrame(records)
    if not existing.empty and 'Date' in existing.columns:
        existing = existing[existing['Date'].astype(str) != date_str]
        ws.clear()
        if not existing.empty: ws.update([existing.columns.values.tolist()] + existing.fillna("").values.tolist())
        else: ws.append_row(["Date", "Start_Time", "End_Time", "Class", "Section", "Subject", "Teacher"])
    fetch_all_routines.clear()

def clear_sheet_cache():
    fetch_sheet_data.clear()
    get_notice.clear()
    fetch_all_routines.clear()
    fetch_exam_schedules.clear()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: ws = sh.worksheet(sheet_name)
    except WorksheetNotFound: ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20); ws.append_row(list(df.columns))
    except Exception: st.error("⚠️ API Busy."); return
    try: ws.append_rows(df.fillna("").astype(str).values.tolist()); clear_sheet_cache()
    except Exception: st.error("⚠️ Submit Failed.")

def overwrite_sheet_df(sheet_name, df):
    try: ws = sh.worksheet(sheet_name)
    except WorksheetNotFound: ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
    except Exception: return
    try: ws.clear(); df = df.fillna("").astype(str); ws.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1') if not df.empty else None; clear_sheet_cache()
    except Exception: st.error("⚠️ Clear Failed.")

@st.cache_data(ttl=600)
def get_notice():
    try: return sh.worksheet("notice").acell("A1").value or ""
    except Exception: return ""

def publish_notice(text):
    try: ws = sh.worksheet("notice")
    except Exception: ws = sh.add_worksheet(title="notice", rows=10, cols=10)
    ws.update_acell("A1", text); clear_sheet_cache()

def get_local_csv(file): return pd.read_csv(file) if os.path.exists(file) else pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        r = get_drive_session().get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        return r.content if r.status_code == 200 else None
    except Exception: return None

def get_secure_photo_uri(url):
    fb = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str): return fb
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match:
        b = fetch_secure_image_bytes(match.group(1))
        if b: return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"
    return url if url.startswith("http") else fb

utc_now = datetime.now(timezone.utc)
now = utc_now + timedelta(hours=5, minutes=30)
curr_date_str, curr_time = now.strftime("%d-%m-%Y"), now.time()

def parse_time_safe(t_str):
    for fmt in ('%H:%M', '%I:%M %p', '%H:%M:%S'):
        try: return datetime.strptime(str(t_str).strip(), fmt).time()
        except Exception: continue
    return None

def highlight_past_holidays(row):
    try:
        h_date = datetime.strptime(str(row['Date']).strip(), "%d-%m-%Y").date()
        if h_date < now.date():
            return ['background-color: #e2e3e5; color: #888888;'] * len(row)
    except Exception:
        pass
    return [''] * len(row)

def render_header():
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        html_str = (
            "<div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px;'>"
            "<img src='data:image/png;base64," + img_b64 + "' style='max-width: 80px; max-height: 80px; object-fit: contain;'>"
            "<div style='text-align: right;'>"
            "<h2 class='header-school-name' style='margin: 0; color: #007bff; font-weight: 900; font-size: 24px; line-height: 1.1;'>BHAGYABANTAPUR</h2>"
            "<h2 class='header-school-name' style='margin: 0; color: #007bff; font-weight: 900; font-size: 20px; line-height: 1.1;'>PRIMARY SCHOOL</h2>"
            "</div></div>"
        )
        st.markdown(html_str, unsafe_allow_html=True)
    else:
        html_str = (
            "<div style='border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px; text-align: center;'>"
            "<h2 style='margin: 0; color: #007bff; font-weight: 900; font-size: 24px;'>BHAGYABANTAPUR PRIMARY SCHOOL</h2>"
            "</div>"
        )
        st.markdown(html_str, unsafe_allow_html=True)

# -------------------------------
# EXECUTE MAIN APPLICATION
# -------------------------------
render_header()
inject_security_css(st.session_state.user_name)

# -------------------------------
# SIDEBAR: MANUAL REFRESH MODULE
# -------------------------------
st.sidebar.markdown("### 🔄 Live Sync")
if st.sidebar.button("🔄 Manual Refresh", use_container_width=True, key="bps_manual_refresh"):
    clear_sheet_cache()
    st.rerun()

# Notice Header
nt = get_notice()
if nt.strip(): st.info(f"📢 NOTICE: {nt}")

# -------------------------------
# TEACHER VIEW
# -------------------------------
if st.session_state.user_role == "teacher":
    t_name_select = st.session_state.user_name
    hd = get_local_csv('holidays.csv')
    is_h = not hd[hd['Date'] == curr_date_str].empty if not hd.empty else False
    
    if is_h or now.strftime('%A') == 'Sunday': 
        st.warning("🏖️ School is closed today.")
    else:
        at_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leave Status", "📅 Holidays"])

        with at_tabs[0]: 
            take_other = st.checkbox("🔄 Take MDM for another class")
            ml = fetch_sheet_data('mdm_log')
            already_sub = False
            
            if not take_other:
                if not ml.empty and 'Date' in ml.columns and 'Teacher' in ml.columns:
                    if not ml[(ml['Date'].astype(str).str.strip() == curr_date_str) & (ml['Teacher'].astype(str).str.strip() == t_name_select)].empty:
                        already_sub = True

            if already_sub: 
                st.success("✅ MDM Submitted for today.")
            else:
                st.subheader("Student MDM Entry")
                tdy = now.strftime('%A')
                mc = TEACHER_INITIALS.get(t_name_select, t_name_select)
                active_rout = get_active_routine(curr_date_str, tdy)
                
                assigned_mdm_classes = []

                if take_other:
                    sc_mdm = st.selectbox("Select Class to Manage", ATTENDANCE_OPTIONS, key='t_mdm_sel')
                    if sc_mdm != "Select Class...":
                        c_name, s_name = sc_mdm.rsplit(' ', 1)
                        assigned_mdm_classes.append({'class': c_name, 'sec': s_name})
                        st.info(f"📌 Override Mode: Managing **{c_name} - {s_name}**")
                else:
                    if not active_rout.empty:
                        active_rout['Start_Obj'] = active_rout['Start_Time'].apply(parse_time_safe)
                        my_1115 = active_rout[(active_rout['Teacher'] == mc) & (active_rout['Start_Obj'] == time(11, 15))]
                        for _, r in my_1115.iterrows():
                            assigned_mdm_classes.append({
                                'class': str(r['Class']).strip(), 
                                'sec': str(r.get('Section', 'A')).strip()
                            })
                            
                if assigned_mdm_classes:
                    primary = assigned_mdm_classes[0]
                    tc, ts = primary['class'], primary['sec']
                    
                    if len(assigned_mdm_classes) > 1 and not take_other:
                        st.warning("⚠️ **You are assigned to MULTIPLE classes for MDM today (Clubbed Classes).** Once you submit this class, please check 'Take MDM for another class' above to submit for the remaining group.")
                    
                    if not take_other:
                        st.info(f"📌 Assigned **11:15 AM** class: **{tc} - {ts}**")

                    sm = fetch_sheet_data('students_master')

                    if not sm.empty:
                        if 'Section' not in sm.columns: sm['Section'] = 'A'
                        if tc == 'CLASS PP': ros = sm[(sm['Class'].isin(['CLASS PP', 'CLASS LPP'])) & (sm['Section'] == ts)].copy()
                        else: ros = sm[(sm['Class'] == tc) & (sm['Section'] == ts)].copy()
                        
                        if not ros.empty:
                            me = ml[(ml['Date'].astype(str) == curr_date_str) & (ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ml['Class'] == tc) & (ml['Section'] == ts)]['Roll'].astype(str).tolist() if not ml.empty else []
                            ros['MDM (Ate)'] = ros['Roll'].astype(str).isin(me)

                            # ----- HISTORICAL DATA CHECK -----
                            mdm_day_counts = {}
                            if not ml.empty:
                                class_cond = ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else (ml['Class'] == tc)
                                hist_ml = ml[class_cond & (ml['Section'] == ts)]
                                mdm_day_counts = hist_ml['Roll'].astype(str).str.strip().value_counts().to_dict()
                                
                            ros['Historical_Count'] = ros['Roll'].astype(str).str.strip().map(lambda x: mdm_day_counts.get(x, 0))
                            # ---------------------------------
                            
                            st.write("📸 **Scan ID Cards (or tick manually below):**")
                            qv = qrcode_scanner(key='at_qr')
                            
                            if st.session_state.scan_msg:
                                st.success(st.session_state.scan_msg)
                                st.session_state.scan_msg = None

                            if qv:
                                should_rerun = False
                                scanned_code = str(qv).strip().upper()
                                
                                # Match the scanned BPS Code against the roster
                                match_df = ros[ros['BPS Code'].astype(str).str.strip().str.upper() == scanned_code]
                                
                                if not match_df.empty:
                                    ar = str(match_df.iloc[0]['Roll']).strip().replace('.0', '')
                                    an = str(match_df.iloc[0]['Name']).strip()
                                    
                                    if str(ar) in me:
                                        st.warning(f"⚠️ {an} is already marked for MDM today!")
                                    else:
                                        chk_key = f"mdm_{ar}_{an}"
                                        if chk_key not in st.session_state.scanned_keys: 
                                            st.session_state.scanned_keys.append(chk_key)
                                            st.session_state[chk_key] = True 
                                            
                                            st.session_state.scan_msg = f"✅ Scanned: {an}. Click 'Submit MDM Data' when done."
                                            should_rerun = True
                                else: 
                                    st.error(f"❌ MISMATCH: Code {scanned_code} is NOT in {tc} {ts}!")
                                    
                                if should_rerun: st.rerun()

                            ros['Scan_Key'] = ros['Roll'].astype(str) + "_" + ros['Name'].astype(str)
                            if 'Thumb_URL' not in ros.columns: ros['Thumb_URL'] = ""
                            with st.spinner("Loading profiles..."):
                                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe: 
                                    ros['Photo'] = list(exe.map(get_secure_photo_uri, ros['Thumb_URL'].tolist()))

                            # Dynamic Splitting using Threshold
                            th_val = get_mdm_threshold()
                            if th_val == "None":
                                regular_ros = ros.copy()
                                not_regular_ros = ros.iloc[0:0].copy()
                            else:
                                th_num = int(th_val)
                                regular_ros = ros[ros['Historical_Count'] >= th_num].copy()
                                not_regular_ros = ros[ros['Historical_Count'] < th_num].copy()

                            st.markdown("### Class Roster (Regular)")
                            cp = st.empty()
                            st.markdown('<div class="roster-container">', unsafe_allow_html=True)
                            sel_mdm, alc = [], 0
                            
                            for _, r in regular_ros.iterrows():
                                c1, c2, c3 = st.columns([1, 4, 2])
                                with c1: st.image(r['Photo'], width=85) 
                                with c2: 
                                    lbl = "<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>" + str(r['Name']) + "</b><br><span style='font-size:12px; color:gray;'>Roll: " + str(r['Roll']) + " | " + str(r['Class']) + "<br>📅 MDM Days: <b>" + str(r['Historical_Count']) + "</b></span></div>"
                                    st.markdown(lbl, unsafe_allow_html=True)
                                with c3:
                                    if r['MDM (Ate)']:
                                        st.markdown("<span style='color:#28a745; font-weight:bold;'>✅ Done</span>", unsafe_allow_html=True)
                                        alc += 1
                                    else:
                                        chk_key = f"mdm_{str(r['Roll']).strip().replace('.0', '')}_{str(r['Name']).strip()}"
                                        
                                        # Ensure Streamlit memory matches our Master List explicitly on render
                                        st.session_state[chk_key] = (chk_key in st.session_state.scanned_keys)
                                        
                                        st.checkbox("Ate MDM", key=chk_key, on_change=t_toggle, args=(chk_key,))
                                        
                                        if chk_key in st.session_state.scanned_keys:
                                            sel_mdm.append(r)
                                st.divider()
                                
                            if not not_regular_ros.empty:
                                with st.expander("⚠️ Show Not Regular Students (" + str(len(not_regular_ros)) + " Students)"):
                                    for _, r in not_regular_ros.iterrows():
                                        c1, c2, c3 = st.columns([1, 4, 2])
                                        with c1: st.image(r['Photo'], width=85) 
                                        with c2: 
                                            lbl = "<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>" + str(r['Name']) + "</b><br><span style='font-size:12px; color:gray;'>Roll: " + str(r['Roll']) + " | " + str(r['Class']) + "<br>📅 MDM Days: <b>" + str(r['Historical_Count']) + "</b></span></div>"
                                            st.markdown(lbl, unsafe_allow_html=True)
                                        with c3:
                                            if r['MDM (Ate)']:
                                                st.markdown("<span style='color:#28a745; font-weight:bold;'>✅ Done</span>", unsafe_allow_html=True)
                                                alc += 1
                                            else:
                                                chk_key = f"mdm_{str(r['Roll']).strip().replace('.0', '')}_{str(r['Name']).strip()}"
                                                
                                                # Ensure Streamlit memory matches our Master List explicitly on render
                                                st.session_state[chk_key] = (chk_key in st.session_state.scanned_keys)
                                                
                                                st.checkbox("Ate MDM", key=chk_key, on_change=t_toggle, args=(chk_key,))
                                                
                                                if chk_key in st.session_state.scanned_keys:
                                                    sel_mdm.append(r)
                                        st.divider()
                            
                            cp.markdown(f"<div class='floating-counter'>✅ Selected: {len(sel_mdm)} | Done: {alc}</div>", unsafe_allow_html=True)
                            st.markdown(f"<h3 style='text-align:center;'>✅ New Selected: {len(sel_mdm)}</h3>", unsafe_allow_html=True)
                            
                            if st.button("Submit MDM Data"):
                                if sel_mdm:
                                    nr = [{'Date': curr_date_str, 'Teacher': t_name_select, 'Class': x['Class'], 'Section': ts, 'Roll': x['Roll'], 'Name': x['Name'], 'Time': now.strftime("%H:%M")} for x in sel_mdm]
                                    append_sheet_df('mdm_log', pd.DataFrame(nr))
                                    
                                    # Memory Cleanup for manual checks
                                    for x in sel_mdm:
                                        roll_c = str(x['Roll']).strip().replace('.0', '')
                                        name_c = str(x['Name']).strip()
                                        chk_key = f"mdm_{roll_c}_{name_c}"
                                        if chk_key in st.session_state:
                                            del st.session_state[chk_key]

                                    st.session_state.scanned_keys = []
                                    st.success(f"Submitted {len(nr)} to Cloud DB!")
                                    st.rerun()
                                else: st.warning("No new students selected.")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            att = fetch_sheet_data('student_attendance_master')
                            if not att.empty and 'Date' in att.columns:
                                ta = att[(att['Date'].astype(str) == curr_date_str) & (att['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else att['Class'] == tc) & (att['Section'] == ts) & (att['Status'] == True)]
                                if not ta.empty: st.markdown(f"<div class='att-badge att-done'>✅ Attendance: {len(ta)}</div>", unsafe_allow_html=True)
                                else: st.markdown("<div class='att-badge att-wait'>⏳ Attendance: Wait</div>", unsafe_allow_html=True)
                        else: st.warning("No students found.")
                else: 
                    if not take_other: st.warning("⚠️ No class at 11:15 AM. MDM Entry disabled.")

        with at_tabs[1]:
            st.subheader("Live Class Status")
            ll = fetch_sheet_data('teacher_leave')
            tdy = now.strftime('%A')
            mc = TEACHER_INITIALS.get(t_name_select, t_name_select)
            active_rout = get_active_routine(curr_date_str, tdy)
            
            if not active_rout.empty and active_rout.iloc[0].get('Is_Exam_Day', False):
                st.success("📝 **EXAM DAY MODE:** Operating on **BPS EXAM** schedule (11:15-12:45 Exam | 12:45-13:30 Next Day Prep | 14:20-15:30 Copies Check). Regular routine is suspended.")
            elif not ll.empty and 'Date' in ll.columns:
                mtl = ll[(ll['Date'] == curr_date_str) & (ll['Teacher'] == t_name_select)]
                if not mtl.empty:
                    ld = mtl.iloc[0]
                    if ld['Type'] not in ['Class Shift / Internal Duty']:
                        st.warning(f"🏖️ You are marked for **{ld['Type']}** today. Follow custom routine if assigned.")
            
            ms = active_rout[active_rout['Teacher'] == mc].copy() if not active_rout.empty else pd.DataFrame()
            
            if not ms.empty:
                ms['Start_Obj'] = ms['Start_Time'].apply(parse_time_safe)
                ms = ms.dropna(subset=['Start_Obj']).sort_values('Start_Obj')
                
                active_classes = []
                for _, r in ms.iterrows():
                    st_time, et = r['Start_Obj'], parse_time_safe(r['End_Time'])
                    if st_time and et and st_time <= curr_time <= et: 
                        active_classes.append(r)
                        
                if active_classes:
                    for cc in active_classes:
                        sty = "border-left: 5px solid #28a745;"
                        px = "🔴 NOW: "
                        if active_rout.iloc[0].get('Is_Exam_Day', False):
                            sty = "border-left: 5px solid #6f42c1; background-color:#f3e8ff;"
                            px = "📝 EXAM SLOT: "
                        elif active_rout.iloc[0].get('Is_Custom', False):
                            sty = "border-left: 5px solid #ffc107; background-color:#fff3cd;"
                            px = "🔄 ASSIGNED: "
                            
                        c_card = "<div class='routine-card' style='" + sty + "'><h3 style='margin:0; color:#333;'>" + px + str(cc['Class']) + " - " + str(cc.get('Section','')) + "</h3><p style='margin:2px 0;'>" + str(cc['Subject']) + "</p><p style='color:gray; font-size:13px; margin:0;'>Ends " + str(cc['End_Time']) + "</p></div>"
                        st.markdown(c_card, unsafe_allow_html=True)
                else: 
                    st.info("☕ No class ongoing.")
                    
                st.divider()
                st.markdown("#### Your Schedule Today")
                def hls(row):
                    if active_rout.iloc[0].get('Is_Exam_Day', False): return ['background-color: #f3e8ff'] * len(row)
                    elif active_rout.iloc[0].get('Is_Custom', False): return ['background-color: #fff3cd'] * len(row)
                    return [''] * len(row)
                st.dataframe(ms[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject']].style.apply(hls, axis=1), hide_index=True)
            else: st.info("No classes scheduled for you today.")

        with at_tabs[2]:
            st.subheader("My Leave Record")
            ll = fetch_sheet_data('teacher_leave')
            if not ll.empty and 'Teacher' in ll.columns:
                ml = ll[ll['Teacher'] == t_name_select]
                c1, c2, c3 = st.columns(3)
                c1.metric("CL Remaining", f"{14 - len(ml[ml['Type'] == 'CL'])}")
                c2.metric("SL Taken", f"{len(ml[ml['Type'] == 'SL'])}")
                c3.metric("Commuted", f"{len(ml[ml['Type'] == 'Commuted Leave'])}")
                st.dataframe(ml[~ml['Type'].isin(['Half Day', 'On Duty', 'School Work', 'Census 2027', 'Class Shift / Internal Duty'])][['Date', 'Type', 'Substitute']], hide_index=True)

        with at_tabs[3]:
            st.subheader("🗓️ School Holiday")
            hd = get_local_csv('holidays.csv')
            if not hd.empty: 
                st.dataframe(hd.style.apply(highlight_past_holidays, axis=1), hide_index=True, use_container_width=True)
            else: 
                st.info("No holiday data available.")

# -------------------------------
# ADMIN VIEW
# -------------------------------
elif st.session_state.user_role == "admin":
    tabs = st.tabs(["📊 Summary", "🍱 MDM Entry", "📝 Attend", "⏳ Live", "🛠️ Routine Maker", "📢 Staff Notice", "📅 Hols", "⚙️ Settings"])
    
    with tabs[0]: 
        st.subheader(f"MDM Status: {curr_date_str}")
        ml = fetch_sheet_data('mdm_log')
        tdy = now.strftime('%A')
        hd = get_local_csv('holidays.csv')
        is_h = not hd[hd['Date'] == curr_date_str].empty if not hd.empty else False
        
        if is_h or tdy == 'Sunday':
            st.info("🏖️ School is closed today. No MDM expected.")
        else:
            active_rout = get_active_routine(curr_date_str, tdy)
            if not active_rout.empty:
                active_rout['Start_Obj'] = active_rout['Start_Time'].apply(parse_time_safe)
                r_1115 = active_rout[active_rout['Start_Obj'] == time(11, 15)]
                
                expected_mdm = {} 
                for _, r in r_1115.iterrows():
                    if str(r['Teacher']).strip() != "--- UNASSIGNED ---":
                        expected_mdm[(r['Class'], r.get('Section', 'A'))] = r['Teacher']
                
                completed_mdm_actual = {}
                today_ml = ml[ml['Date'].astype(str) == curr_date_str] if not ml.empty else pd.DataFrame()
                if not today_ml.empty:
                    for _, r in today_ml.iterrows():
                        c = str(r['Class']).strip()
                        if c == 'CLASS LPP': c = 'CLASS PP'
                        s = str(r.get('Section', 'A')).strip()
                        t_actual = str(r.get('Teacher', '')).strip()
                        completed_mdm_actual[(c, s)] = t_actual
                        
                status_data = []
                for (c, s), t_init in expected_mdm.items():
                    assigned_full = INV_TEACHER_INITIALS.get(t_init, t_init)
                    if (c, s) in completed_mdm_actual:
                        status_data.append({
                            'Class': f"{c} {s}".strip(),
                            'Assigned Teacher': assigned_full,
                            'Completed By': completed_mdm_actual[(c, s)],
                            'Status': '✅ Done'
                        })
                    else:
                        status_data.append({
                            'Class': f"{c} {s}".strip(),
                            'Assigned Teacher': assigned_full,
                            'Completed By': '---',
                            'Status': '❌ Pending'
                        })
                        
                for (c, s), actual_full in completed_mdm_actual.items():
                    if (c, s) not in expected_mdm:
                        status_data.append({
                            'Class': f"{c} {s}".strip(),
                            'Assigned Teacher': '--- (Override)',
                            'Completed By': actual_full,
                            'Status': '✅ Done'
                        })
                
                if status_data:
                    st.markdown("##### 📝 Today's MDM Submission Tracker")
                    status_df = pd.DataFrame(status_data)
                    
                    def highlight_status(row):
                        if row['Status'] == '✅ Done': return ['background-color: #d4edda; color: #155724; font-weight: bold'] * len(row)
                        else: return ['background-color: #f8d7da; color: #721c24'] * len(row)
                            
                    st.dataframe(status_df.style.apply(highlight_status, axis=1), hide_index=True, use_container_width=True)
                    
                    pending_count = len(status_df[status_df['Status'] == '❌ Pending'])
                    if pending_count > 0: st.error(f"🚨 **Action Required:** {pending_count} class(es) have NOT submitted MDM today!")
                    else: st.success("🎉 All expected MDM entries for today are completed!")
        
        st.divider()
        al = fetch_sheet_data('student_attendance_master') 
        c1, c2 = st.columns([2, 1])
        vd = c1.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
        sa = c2.checkbox("Show All")
        fm = ml if sa else ml[ml['Date'].astype(str) == vd].copy() if not ml.empty else pd.DataFrame()
        fa = al[al['Status'] == True] if sa else al[(al['Date'].astype(str) == vd) & (al['Status'] == True)].copy() if not al.empty else pd.DataFrame()
        cf = "All"
        if not fm.empty or not fa.empty:
            mc = fm.groupby(['Class', 'Section']).size().reset_index(name='MDM Entry') if not fm.empty else pd.DataFrame(columns=['Class', 'Section', 'MDM Entry'])
            ac = fa.groupby(['Class', 'Section']).size().reset_index(name='Attendance') if not fa.empty else pd.DataFrame(columns=['Class', 'Section', 'Attendance'])
            sd = pd.merge(ac, mc, on=['Class', 'Section'], how='outer').fillna(0).infer_objects(copy=False)
            sd['Attendance'], sd['MDM Entry'] = sd['Attendance'].astype(int), sd['MDM Entry'].astype(int)
            sd.sort_values(by=['Class', 'Section'], inplace=True)
            if not sd.empty: sd = pd.concat([sd, pd.DataFrame([{'Class': 'TOTAL', 'Section': '', 'Attendance': sd['Attendance'].sum(), 'MDM Entry': sd['MDM Entry'].sum()}])], ignore_index=True)
            st.markdown(f"##### 🏫 Breakdown for {vd if not sa else 'All Time'}")
            st.dataframe(sd, hide_index=True, use_container_width=True)
            st.markdown("##### 📄 Detailed List")
            if not fm.empty:
                fm['Class_Sec'] = fm['Class'].astype(str) + " " + fm['Section'].astype(str)
                cf = st.selectbox("Filter Class", ["All"] + sorted(fm['Class_Sec'].unique()))
                ddf = fm[fm['Class_Sec'] == cf] if cf != "All" else fm
                st.dataframe(ddf[['Date', 'Class', 'Section', 'Roll', 'Name']], hide_index=True)
        else: st.info("No data available for this date.")
        st.divider()
        if st.button(f"🗑️ Clear Data ({cf})"):
            tm = fetch_sheet_data('mdm_log')
            if not tm.empty:
                if cf == "All": tm = tm[tm['Date'].astype(str) != curr_date_str]
                else: tm = tm[~((tm['Date'].astype(str) == curr_date_str) & ((tm['Class'].astype(str) + " " + tm['Section'].astype(str)) == cf))]
                overwrite_sheet_df('mdm_log', tm); st.success("Cleared!"); st.rerun()

    with tabs[1]:
        st.subheader("Admin MDM Entry (Late/Missed)")
        sc_mdm = st.selectbox("Mark MDM for Class", ATTENDANCE_OPTIONS, key='adm_mdm_sel')
        if sc_mdm != "Select Class...":
            tc, ts = sc_mdm.rsplit(' ', 1)
            sm = fetch_sheet_data('students_master')
            ml = fetch_sheet_data('mdm_log')
            if not sm.empty:
                if 'Section' not in sm.columns: sm['Section'] = 'A'
                if tc == 'CLASS PP': ros = sm[(sm['Class'].isin(['CLASS PP', 'CLASS LPP'])) & (sm['Section'] == ts)].copy()
                else: ros = sm[(sm['Class'] == tc) & (sm['Section'] == ts)].copy()
                
                if not ros.empty:
                    me = ml[(ml['Date'].astype(str) == curr_date_str) & (ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ml['Class'] == tc) & (ml['Section'] == ts)]['Roll'].astype(str).tolist() if not ml.empty else []
                    ros['MDM (Ate)'] = ros['Roll'].astype(str).isin(me)
                    
                    # ----- HISTORICAL DATA CHECK -----
                    mdm_day_counts = {}
                    if not ml.empty:
                        class_cond = ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else (ml['Class'] == tc)
                        hist_ml = ml[class_cond & (ml['Section'] == ts)]
                        mdm_day_counts = hist_ml['Roll'].astype(str).str.strip().value_counts().to_dict()
                        
                    ros['Historical_Count'] = ros['Roll'].astype(str).str.strip().map(lambda x: mdm_day_counts.get(x, 0))
                    # ---------------------------------
                    
                    st.write("📸 **Scan Missed ID Cards (or tick manually below):**")
                    qv = qrcode_scanner(key='adm_mdm_qr')
                    
                    if st.session_state.admin_scan_msg:
                        st.success(st.session_state.admin_scan_msg)
                        st.session_state.admin_scan_msg = None
                        
                    if qv:
                        should_rerun = False
                        scanned_code = str(qv).strip().upper()
                        
                        # Match the scanned BPS Code against the roster
                        match_df = ros[ros['BPS Code'].astype(str).str.strip().str.upper() == scanned_code]
                        
                        if not match_df.empty:
                            ar = str(match_df.iloc[0]['Roll']).strip().replace('.0', '')
                            an = str(match_df.iloc[0]['Name']).strip()
                            
                            if str(ar) in me:
                                st.warning(f"⚠️ {an} is already marked for MDM today!")
                            else:
                                chk_key = f"adm_mdm_{ar}_{an}"
                                if chk_key not in st.session_state.admin_scanned_keys: 
                                    st.session_state.admin_scanned_keys.append(chk_key)
                                    st.session_state[chk_key] = True 
                                    
                                    st.session_state.admin_scan_msg = f"✅ Scanned: {an}. Scan next or Click 'Submit Admin MDM Data' when done."
                                    should_rerun = True
                        else: 
                            st.error(f"❌ MISMATCH: Code {scanned_code} is NOT in {tc} {ts}!")
                            
                        if should_rerun: st.rerun()

                    ros['Scan_Key'] = ros['Roll'].astype(str) + "_" + ros['Name'].astype(str)
                    if 'Thumb_URL' not in ros.columns: ros['Thumb_URL'] = ""
                    with st.spinner("Loading profiles..."):
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe: 
                            ros['Photo'] = list(exe.map(get_secure_photo_uri, ros['Thumb_URL'].tolist()))

                    th_val = get_mdm_threshold()
                    if th_val == "None":
                        regular_ros = ros.copy()
                        not_regular_ros = ros.iloc[0:0].copy()
                    else:
                        th_num = int(th_val)
                        regular_ros = ros[ros['Historical_Count'] >= th_num].copy()
                        not_regular_ros = ros[ros['Historical_Count'] < th_num].copy()

                    st.markdown("### Class Roster (Regular)")
                    cp = st.empty()
                    st.markdown('<div class="roster-container">', unsafe_allow_html=True)
                    sel_mdm, alc = [], 0
                    
                    for _, r in regular_ros.iterrows():
                        c1, c2, c3 = st.columns([1, 4, 2])
                        with c1: st.image(r['Photo'], width=85) 
                        with c2: 
                            lbl = "<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>" + str(r['Name']) + "</b><br><span style='font-size:12px; color:gray;'>Roll: " + str(r['Roll']) + " | " + str(r['Class']) + "<br>📅 MDM Days: <b>" + str(r['Historical_Count']) + "</b></span></div>"
                            st.markdown(lbl, unsafe_allow_html=True)
                        with c3:
                            if r['MDM (Ate)']:
                                st.markdown("<span style='color:#28a745; font-weight:bold;'>✅ Done</span>", unsafe_allow_html=True)
                                alc += 1
                            else:
                                chk_key = f"adm_mdm_{str(r['Roll']).strip().replace('.0', '')}_{str(r['Name']).strip()}"
                                
                                # Ensure Streamlit memory matches our Master List explicitly on render
                                st.session_state[chk_key] = (chk_key in st.session_state.admin_scanned_keys)
                                
                                st.checkbox("Ate MDM", key=chk_key, on_change=a_toggle, args=(chk_key,))
                                
                                if chk_key in st.session_state.admin_scanned_keys:
                                    sel_mdm.append(r)
                        st.divider()
                        
                    if not not_regular_ros.empty:
                        with st.expander("⚠️ Show Not Regular Students (" + str(len(not_regular_ros)) + " Students)"):
                            for _, r in not_regular_ros.iterrows():
                                c1, c2, c3 = st.columns([1, 4, 2])
                                with c1: st.image(r['Photo'], width=85) 
                                with c2: 
                                    lbl = "<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>" + str(r['Name']) + "</b><br><span style='font-size:12px; color:gray;'>Roll: " + str(r['Roll']) + " | " + str(r['Class']) + "<br>📅 MDM Days: <b>" + str(r['Historical_Count']) + "</b></span></div>"
                                    st.markdown(lbl, unsafe_allow_html=True)
                                with c3:
                                    if r['MDM (Ate)']:
                                        st.markdown("<span style='color:#28a745; font-weight:bold;'>✅ Done</span>", unsafe_allow_html=True)
                                        alc += 1
                                    else:
                                        chk_key = f"adm_mdm_{str(r['Roll']).strip().replace('.0', '')}_{str(r['Name']).strip()}"
                                        
                                        # Ensure Streamlit memory matches our Master List explicitly on render
                                        st.session_state[chk_key] = (chk_key in st.session_state.admin_scanned_keys)
                                        
                                        st.checkbox("Ate MDM", key=chk_key, on_change=a_toggle, args=(chk_key,))
                                        
                                        if chk_key in st.session_state.admin_scanned_keys:
                                            sel_mdm.append(r)
                                        st.divider()
                    
                    cp.markdown(f"<div class='floating-counter'>✅ Selected: {len(sel_mdm)} | Done: {alc}</div>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center;'>✅ New Selected: {len(sel_mdm)}</h3>", unsafe_allow_html=True)
                    
                    if st.button("Submit Admin MDM Data"):
                        if sel_mdm:
                            nr = [{'Date': curr_date_str, 'Teacher': f"{st.session_state.user_name} (Admin)", 'Class': x['Class'], 'Section': ts, 'Roll': x['Roll'], 'Name': x['Name'], 'Time': now.strftime("%H:%M")} for x in sel_mdm]
                            append_sheet_df('mdm_log', pd.DataFrame(nr))
                            
                            # Memory Cleanup for manual checks
                            for x in sel_mdm:
                                roll_c = str(x['Roll']).strip().replace('.0', '')
                                name_c = str(x['Name']).strip()
                                chk_key = f"adm_mdm_{roll_c}_{name_c}"
                                if chk_key in st.session_state:
                                    del st.session_state[chk_key]

                            st.session_state.admin_scanned_keys = []
                            st.success(f"Added {len(nr)} late entries to Cloud DB!")
                            st.rerun()
                        else: st.warning("No new students selected.")
                    st.markdown('</div>', unsafe_allow_html=True)
                else: st.warning("No students found.")

    with tabs[2]:
        st.subheader("Student Attendance")
        sc = st.selectbox("Mark Attendance", ATTENDANCE_OPTIONS, key='ht_att')
        if sc != "Select Class...":
            tc, ts = sc.rsplit(' ', 1)
            sm = fetch_sheet_data('students_master')
            ml = fetch_sheet_data('mdm_log')
            if not sm.empty:
                if 'Section' not in sm.columns: sm['Section'] = 'A'
                if tc == 'CLASS PP': ros = sm[(sm['Class'].isin(['CLASS PP', 'CLASS LPP'])) & (sm['Section'] == ts)].copy()
                else: ros = sm[(sm['Class'] == tc) & (sm['Section'] == ts)].copy()
                
                if not ros.empty:
                    me = ml[(ml['Date'].astype(str) == curr_date_str) & (ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ml['Class'] == tc) & (ml['Section'] == ts)]['Roll'].astype(str).tolist() if not ml.empty else []
                    ros['MDM (Ate)'] = ros['Roll'].astype(str).isin(me)
                    
                    mdm_day_counts = {}
                    if not ml.empty:
                        class_cond = ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else (ml['Class'] == tc)
                        hist_ml = ml[class_cond & (ml['Section'] == ts)]
                        mdm_day_counts = hist_ml['Roll'].astype(str).str.strip().value_counts().to_dict()
                    
                    if 'Thumb_URL' not in ros.columns: ros['Thumb_URL'] = ""
                    with st.spinner("Loading profiles..."):
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe: ros['Photo'] = list(exe.map(get_secure_photo_uri, ros['Thumb_URL'].tolist()))
                    
                    th_val = get_mdm_threshold()

                    st.markdown("### Class Roster")
                    cp = st.empty()
                    st.markdown('<div class="roster-container">', unsafe_allow_html=True)
                    ad, pc = [], 0
                    for _, r in ros.iterrows():
                        roll_str = str(r['Roll']).strip()
                        days_attended = mdm_day_counts.get(roll_str, 0)
                        
                        if th_val == "None":
                            default_present = False
                        else:
                            default_present = days_attended >= int(th_val)
                        
                        c1, c2, c3 = st.columns([1, 4, 2.5])
                        with c1: st.image(r['Photo'], width=85) 
                        with c2: 
                            label_html = "<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>" + str(r['Name']) + "</b><br><span style='font-size:12px; color:gray;'>Roll: " + str(r['Roll']) + " | " + str(r['Class']) + "<br>📅 MDM Days: <b>" + str(days_attended) + "</b></span></div>"
                            st.markdown(label_html, unsafe_allow_html=True)
                        with c3:
                            ip = st.checkbox("Present", value=default_present, key=f"att_{r['Roll']}_{r['Name']}")
                            if ip: pc += 1
                            st.checkbox("MDM Entry", value=bool(r['MDM (Ate)']), disabled=True, key=f"mdm_ro_{r['Roll']}_{r['Name']}")
                            ad.append({'Date': curr_date_str, 'Class': r['Class'], 'Section': ts, 'Roll': r['Roll'], 'Name': r['Name'], 'Status': ip})
                        st.divider()
                    
                    cp.markdown(f"<div class='floating-counter'>✅ Present: {pc}</div>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center;'>✅ Total Present: {pc}</h3>", unsafe_allow_html=True)
                    if st.button(f"Save Attendance"):
                        append_sheet_df('student_attendance_master', pd.DataFrame(ad)); st.success("Saved."); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                    ac = fetch_sheet_data('student_attendance_master')
                    is_sub = not ac[(ac['Date'].astype(str) == curr_date_str) & (ac['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ac['Class'] == tc) & (ac['Section'] == ts)].empty if not ac.empty else False
                    if is_sub:
                        st.info(f"🔒 Attendance is submitted.")
                        if st.button("🗑️ Clear Today's Attendance"):
                            ta = ac[~((ac['Date'].astype(str) == curr_date_str) & (ac['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ac['Class'] == tc) & (ac['Section'] == ts))]
                            overwrite_sheet_df('student_attendance_master', ta); st.rerun()

        st.divider()
        st.subheader("📊 Daily Report")
        al = fetch_sheet_data('student_attendance_master')
        avd = st.date_input("Report Date", datetime.now(), key="att_d").strftime("%d-%m-%Y")
        if not al.empty:
            ta = al[(al['Date'].astype(str) == avd) & (al['Status'] == True)]
            if not ta.empty:
                p = len(ta[ta['Class'].isin(['CLASS PP', 'CLASS LPP'])])
                i4 = len(ta[ta['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])])
                v = len(ta[ta['Class'] == 'CLASS V'])
                
                tbl_html = "<table class='report-table'><tr><th>Class PP</th><th>I-IV</th><th>Class V</th><th>TOTAL</th></tr><tr><td>" + str(p) + "</td><td>" + str(i4) + "</td><td>" + str(v) + "</td><td><b>" + str(p+i4+v) + "</b></td></tr></table>"
                st.markdown(tbl_html, unsafe_allow_html=True)
            else: st.info(f"No attendance for {avd}.")

    with tabs[3]: 
        st.subheader(f"🏫 Live Master Routine")
        tdy = now.strftime('%A')
        active_rout = get_active_routine(curr_date_str, tdy)
        
        if not active_rout.empty:
            active_rout['Start_Obj'] = active_rout['Start_Time'].apply(parse_time_safe)
            active_rout['End_Obj'] = active_rout['End_Time'].apply(parse_time_safe)
            active_rout = active_rout.dropna(subset=['Start_Obj', 'End_Obj']).sort_values('Start_Obj')
            
            is_exam_day = active_rout.iloc[0].get('Is_Exam_Day', False)
            is_custom = active_rout.iloc[0].get('Is_Custom', False)
            
            if is_exam_day:
                st.success("📝 **EXAM DAY ROUTINE ACTIVE:** Operating on automatic **BPS EXAM** schedule (11:15-12:45 Exam | 12:45-13:30 Next Day Prep | 14:20-15:30 Copies Check).")
            elif is_custom:
                st.success("🟢 Operating on Custom Generated Routine for today.")
            
            lc = []
            for _, r in active_rout.iterrows():
                if r['Start_Obj'] <= curr_time <= r['End_Obj']:
                    lc.append(r)
                    
            st.markdown("### 🔴 LIVE NOW")
            if lc:
                cls = st.columns(2)
                for i, r in enumerate(lc):
                    is_sub = is_custom and r['Teacher'] != "--- UNASSIGNED ---"
                    tn = f"👨‍🏫 {INV_TEACHER_INITIALS.get(r['Teacher'], r['Teacher'])}"
                    if r['Teacher'] == "--- UNASSIGNED ---": tn = "🚫 UNASSIGNED"
                    
                    sty = "border-left: 5px solid #28a745;"
                    if is_exam_day: sty = "border-left: 5px solid #6f42c1; background-color:#f3e8ff;"
                    elif is_sub: sty = "border-left: 5px solid #ffc107; background-color:#fff3cd;"
                    
                    c_card = "<div class='routine-card' style='" + sty + "'><h4 style='margin:0;'>" + str(r['Class']) + " " + str(r.get('Section', '')) + "</h4><p style='margin:0; font-weight:bold;'>" + str(tn) + "</p><p style='margin:0; font-size:12px; color:gray;'>" + str(r['Subject']) + " | Ends: " + str(r['End_Time']) + "</p></div>"
                    cls[i%2].markdown(c_card, unsafe_allow_html=True)
            else: 
                st.info("☕ No classes ongoing.")
                
            st.dataframe(active_rout[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject', 'Teacher']], hide_index=True)
        else:
            st.warning("No routine found for today.")

    with tabs[4]: 
        st.subheader("🛠️ 3-Step Daily Routine Planner")
        sds = st.date_input("Select Date to Manage", datetime.now())
        sds_str = sds.strftime("%d-%m-%Y")
        tdy_name = sds.strftime('%A')
        
        st.markdown("### Step 1: Manage Absences")
        ll = fetch_sheet_data('teacher_leave')
        el = ll[ll['Date'] == sds_str]['Teacher'].tolist() if not ll.empty and 'Date' in ll.columns else []
        
        absent_teachers = st.multiselect("Select Absent Teachers", TEACHER_LIST, default=[t for t in el if t in TEACHER_LIST])
        
        if absent_teachers:
            leave_types = {}
            cols = st.columns(min(len(absent_teachers), 3))
            for i, t in enumerate(absent_teachers):
                prev_type = "CL"
                if t in el: prev_type = ll[(ll['Date'] == sds_str) & (ll['Teacher'] == t)]['Type'].iloc[0]
                opts = ["CL", "SL", "Commuted Leave", "Half Day", "On Duty", "School Work", "Census 2027", "Class Shift / Internal Duty"]
                idx = opts.index(prev_type) if prev_type in opts else 0
                leave_types[t] = cols[i%3].selectbox(f"Type: {t}", opts, index=idx, key=f"lt_{t}")
            
            if st.button("💾 Save Absences"):
                new_ll = ll[ll['Date'] != sds_str] if not ll.empty and 'Date' in ll.columns else ll.copy() if not ll.empty else pd.DataFrame(columns=["Date", "Teacher", "Type", "Substitute", "Detailed_Sub_Log"])
                new_records = []
                for t in absent_teachers:
                    new_records.append({"Date": sds_str, "Teacher": t, "Type": leave_types[t], "Substitute": "Managed via Custom Routine", "Detailed_Sub_Log": "See bps_routine (daily_override)"})
                if new_records:
                    new_ll = pd.concat([new_ll, pd.DataFrame(new_records)], ignore_index=True)
                overwrite_sheet_df('teacher_leave', new_ll)
                st.success("Absences Saved! Move to Step 2.")
                st.rerun()
                
        st.markdown("---")
        st.markdown("### Step 2: Class Size Reference (MDM Data)")
        st.caption("Use this latest MDM data to strategically decide which classes to combine.")
        
        ml = fetch_sheet_data('mdm_log')
        classes_ref = ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
        summary = []
        if ml.empty or 'Date' not in ml.columns:
            for c in classes_ref: summary.append({"Class": c, "Latest MDM Count": 0, "Data Source": "No Data"})
        else:
            ml['DateObj'] = pd.to_datetime(ml['Date'], format='%d-%m-%Y', errors='coerce')
            target_obj = datetime.strptime(sds_str, "%d-%m-%Y")
            for c in classes_ref:
                c_ml = ml[ml['Class'] == c]
                if c_ml.empty:
                    summary.append({"Class": c, "Latest MDM Count": 0, "Data Source": "No Data"})
                    continue
                t_ml = c_ml[c_ml['Date'] == sds_str]
                if not t_ml.empty:
                    summary.append({"Class": c, "Latest MDM Count": len(t_ml), "Data Source": "Today"})
                else:
                    p_ml = c_ml[c_ml['DateObj'] < target_obj]
                    if not p_ml.empty:
                        max_d = p_ml['DateObj'].max()
                        count = len(p_ml[p_ml['DateObj'] == max_d])
                        summary.append({"Class": c, "Latest MDM Count": count, "Data Source": f"Past ({max_d.strftime('%d-%m-%Y')})"})
                    else:
                        summary.append({"Class": c, "Latest MDM Count": 0, "Data Source": "No Data"})
                        
        st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Step 3: Build Custom Routine")
        st.caption("💡 **Tip to Combine Classes:** Do not edit the class names. Just assign the *same teacher* to multiple classes in the same time slot.")
        
        active_rout = get_active_routine(sds_str, tdy_name)
        
        if active_rout.empty:
            st.warning("No base routine found for this day to edit.")
        else:
            is_exam_day = active_rout.iloc[0].get('Is_Exam_Day', False)
            is_custom = active_rout.iloc[0].get('Is_Custom', False)
            
            if is_exam_day: st.info("📝 **Exam Day Schedule Active:** This routine is automatically driven by the **BPS EXAM** schedule.")
            elif is_custom: st.success("🟢 Currently editing the **Custom Routine** for this date.")
            else: st.info("🔵 Currently showing the **Default Routine**. Edits below will create a Custom Routine.")
            
            edit_df = active_rout[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject', 'Teacher']].copy()
            
            if not is_custom and not is_exam_day:
                for t in absent_teachers:
                    t_init = TEACHER_INITIALS.get(t, t)
                    edit_df.loc[edit_df['Teacher'] == t_init, 'Teacher'] = "--- UNASSIGNED ---"
                    
            edited_rout = st.data_editor(
                edit_df,
                num_rows="dynamic",
                column_config={
                    "Teacher": st.column_config.SelectboxColumn("Assigned Teacher", options=["--- UNASSIGNED ---"] + list(TEACHER_INITIALS.values())),
                },
                use_container_width=True
            )
            
            if st.button("💾 Save Custom Routine for " + sds_str):
                save_daily_routine(sds_str, edited_rout)
                st.success("Custom Routine Saved! All teacher dashboards are now synced.")
                st.rerun()
                
            if is_custom and not is_exam_day and st.button("🗑️ Revert & Delete Custom Routine"):
                delete_daily_routine(sds_str)
                st.success("Reverted to default schedule.")
                st.rerun()

    with tabs[5]: 
        st.subheader("📢 Staff Notice")
        n = st.text_area("Notice", get_notice())
        if st.button("Publish to Cloud"): publish_notice(n); st.success("Published!")

    with tabs[6]: 
        st.subheader("🗓️ School Holiday")
        hd = get_local_csv('holidays.csv')
        if not hd.empty: 
            st.data_editor(hd.style.apply(highlight_past_holidays, axis=1), hide_index=True, num_rows="dynamic", key="h_edit", use_container_width=True)
        else: 
            st.info("No data.")
        
    with tabs[7]:
        st.subheader("⚙️ System Settings")
        st.markdown("Control the **Regular Student** criteria. If a student has attended MDM this many times, they will appear in the Regular list and be checked 'Present' by default.")
        curr_th = get_mdm_threshold()
        opts = ["None"] + [str(i) for i in range(21)]
        idx = opts.index(curr_th) if curr_th in opts else 1
        new_th = st.selectbox("Minimum MDM Days to be 'Regular'", options=opts, index=idx)
        
        if st.button("💾 Save Settings", type="primary"):
            set_setting("MDM_REGULAR_THRESHOLD", new_th)
            st.success("Settings saved! Threshold updated.")
            clear_sheet_cache()
            st.rerun()
