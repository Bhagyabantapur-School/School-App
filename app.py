import streamlit as st
import pandas as pd
import os
import calendar
from datetime import datetime, time, timedelta
from streamlit_qrcode_scanner import qrcode_scanner
import gspread
from google.oauth2.service_account import Credentials

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
        .block-container {{ padding-top: 1rem; max-width: 650px; }}
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
def init_gsheets():
    try:
        skey = dict(st.secrets["gcp_service_account"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(skey, scopes=scopes)
        gc = gspread.authorize(credentials)
        return gc.open("BPS_Database")
    except Exception as e:
        st.error("⚠️ Google Sheets Connection Failed! Please check your Streamlit Secrets.")
        st.stop()

sh = init_gsheets()

@st.cache_data(ttl=5) # Refreshes every 5 seconds to get live data
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        # Automatically convert string TRUE/FALSE back to python booleans
        df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}, inplace=True)
        return df
    except:
        return pd.DataFrame()

def clear_sheet_cache():
    fetch_sheet_data.clear()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: ws = sh.worksheet(sheet_name)
    except:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    
    df = df.fillna("").astype(str)
    ws.append_rows(df.values.tolist())
    clear_sheet_cache()

def overwrite_sheet_df(sheet_name, df):
    try: ws = sh.worksheet(sheet_name)
    except: ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
    
    ws.clear()
    df = df.fillna("").astype(str)
    if not df.empty:
        ws.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1')
    clear_sheet_cache()

def get_notice():
    try: return sh.worksheet("notice").acell("A1").value or ""
    except: return ""

def publish_notice(text):
    try: ws = sh.worksheet("notice")
    except: ws = sh.add_worksheet(title="notice", rows=10, cols=10)
    ws.update_acell("A1", text)

# Local static files (Uploaded via GitHub)
def get_local_csv(file):
    if os.path.exists(file): 
        try: return pd.read_csv(file)
        except: return pd.DataFrame()
    return pd.DataFrame()

# --- 4. TIME HELPERS ---
utc_now = datetime.utcnow()
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
            
            at_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leave Status", "📅 Holidays"])

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
                        
                        students = get_local_csv('students.csv')
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

                                roster['Scan_Key'] = roster['Roll'].astype(str) + "_" + roster['Name'].astype(str)
                                roster['Ate_MDM'] = roster['Scan_Key'].isin(st.session_state.scanned_keys)
                                
                                edited = st.data_editor(roster[['Section', 'Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
                                st.markdown(f"### ✅ Total Selected: {edited['Ate_MDM'].sum()}")

                                if st.button("Submit MDM"):
                                    ate = edited[edited['Ate_MDM'] == True]
                                    new_rows = [{'Date': curr_date_str, 'Teacher': t_name_select, 'Class': target_class, 'Section': target_section, 'Roll': r['Roll'], 'Name': r['Name'], 'Time': now.strftime("%H:%M")} for _, r in ate.iterrows()]
                                    
                                    if new_rows:
                                        append_sheet_df('mdm_log', pd.DataFrame(new_rows))
                                        st.session_state.scanned_keys = []
                                        st.success(f"Submitted {len(new_rows)} students to Cloud DB!")
                                        st.rerun()
                                    else: st.warning("No students selected.")
                                
                                att_df = fetch_sheet_data('student_attendance_master')
                                is_att_marked = False
                                att_count = 0
                                if not att_df.empty and 'Date' in att_df.columns:
                                    todays_att = att_df[(att_df['Date'].astype(str) == curr_date_str) & (att_df['Class'] == target_class) & (att_df['Section'] == target_section) & (att_df['Status'] == True)]
                                    if not todays_att.empty:
                                        is_att_marked, att_count = True, len(todays_att)
                                
                                if is_att_marked: st.markdown(f"<div class='att-badge att-done'>✅ Attendance: {att_count}</div>", unsafe_allow_html=True)
                                else: st.markdown("<div class='att-badge att-wait'>⏳ Attendance: Wait</div>", unsafe_allow_html=True)
                            else: st.warning("No students found.")
                    else: st.warning("⚠️ No class at 11:15 AM. MDM Entry disabled.")

            with at_tabs[1]: # Routine
                st.subheader("Live Class Status")
                leave_log = fetch_sheet_data('teacher_leave')
                routine = get_local_csv('routine.csv')
                
                on_leave, leave_details = False, None
                if not leave_log.empty and 'Date' in leave_log.columns:
                    my_today_leave = leave_log[(leave_log['Date'] == curr_date_str) & (leave_log['Teacher'] == t_name_select)]
                    if not my_today_leave.empty: on_leave, leave_details = True, my_today_leave.iloc[0]
                
                if on_leave:
                    st.warning(f"🏖️ You are marked **{leave_details['Type']}** today.")
                    raw_subs = str(leave_details.get('Detailed_Sub_Log', ''))
                    if raw_subs and raw_subs != "None":
                        st.markdown("### 🤝 Substitution Plan")
                        for assign in raw_subs.split(" | "):
                            parts = assign.split(": ")
                            if len(parts) == 2: st.markdown(f"<div class='sub-card'><b>{parts[0].strip()}</b> covered by <b>{parts[1].strip()}</b></div>", unsafe_allow_html=True)
                    else: st.info("No specific substitutes assigned yet.")
                else:
                    my_code = TEACHER_INITIALS.get(t_name_select, t_name_select)
                    today_day = now.strftime('%A')
                    
                    my_schedule = routine[(routine['Teacher'] == my_code) & (routine['Day'] == today_day)].copy() if not routine.empty else pd.DataFrame()
                    if not my_schedule.empty: my_schedule['Is_Sub'] = False
                    
                    sub_duties = []
                    if not leave_log.empty:
                        for _, row in leave_log[leave_log['Date'] == curr_date_str].iterrows():
                            if t_name_select in str(row['Detailed_Sub_Log']):
                                absent_code = TEACHER_INITIALS.get(row['Teacher'], "")
                                for assign in str(row['Detailed_Sub_Log']).split(" | "):
                                    if f": {t_name_select}" in assign:
                                        slot_time = assign.split(": ")[0].strip()
                                        orig_class = routine[(routine['Teacher'] == absent_code) & (routine['Day'] == today_day) & (routine['Start_Time'] == slot_time)]
                                        if not orig_class.empty:
                                            r = orig_class.iloc[0]
                                            sub_duties.append({'Start_Time': r['Start_Time'], 'End_Time': r['End_Time'], 'Class': r['Class'], 'Section': r.get('Section', 'A'), 'Subject': f"🔄 Sub for {row['Teacher']}", 'Teacher': my_code, 'Day': today_day, 'Is_Sub': True})
                    
                    if sub_duties: my_schedule = pd.concat([my_schedule, pd.DataFrame(sub_duties)], ignore_index=True)
                    
                    if not my_schedule.empty:
                        my_schedule['Start_Obj'] = my_schedule['Start_Time'].apply(parse_time_safe)
                        my_schedule = my_schedule.dropna(subset=['Start_Obj']).sort_values('Start_Obj')
                        current_class, next_class = None, None
                        for _, row in my_schedule.iterrows():
                            s_time, e_time = row['Start_Obj'], parse_time_safe(row['End_Time'])
                            if s_time and e_time:
                                if s_time <= curr_time <= e_time: current_class = row
                                elif s_time > curr_time:
                                    next_class = row; break
                        
                        if current_class is not None:
                            style = "border-left: 5px solid #ffc107; background-color:#fff3cd;" if current_class['Is_Sub'] else "border-left: 5px solid #28a745;"
                            prefix = "🔄 SUB: " if current_class['Is_Sub'] else "🔴 NOW: "
                            st.markdown(f"""<div class="routine-card" style="{style}"><h3 style="margin:0; color:#333;">{prefix}{current_class['Class']} - {current_class.get('Section','')}</h3><p>{current_class['Subject']}</p><p style="color:gray;">Ends {current_class['End_Time']}</p></div>""", unsafe_allow_html=True)
                        else: st.info("☕ No class ongoing.")

                        st.divider()
                        def highlight_subs(row): return ['background-color: #fff3cd'] * len(row) if str(row['Subject']).startswith('🔄') else [''] * len(row)
                        st.dataframe(my_schedule[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject']].style.apply(highlight_subs, axis=1), hide_index=True)
                    else: st.info("No classes today.")

            with at_tabs[2]: # Leaves
                st.subheader("My Leave Record")
                leave_log = fetch_sheet_data('teacher_leave')
                if not leave_log.empty and 'Teacher' in leave_log.columns:
                    my_leaves = leave_log[leave_log['Teacher'] == t_name_select]
                    c1, c2 = st.columns(2)
                    c1.metric("CL Remaining", f"{14 - len(my_leaves[my_leaves['Type'] == 'CL'])}")
                    c2.metric("SL Taken", f"{len(my_leaves[my_leaves['Type'] == 'SL'])}")
                    st.dataframe(my_leaves[~my_leaves['Type'].isin(['Half Day', 'On Duty'])][['Date', 'Type', 'Substitute']], hide_index=True)
            
            with at_tabs[3]: # Holidays
                st.subheader("🗓️ School Holiday List")
                h_df = get_local_csv('holidays.csv')
                if not h_df.empty: st.table(h_df)
                else: st.info("No holiday data available.")

    # ==========================================
    # HEAD TEACHER (ADMIN) DASHBOARD
    # ==========================================
    elif st.session_state.user_role == "admin":
        tabs = st.tabs(["📊 Summary & MDM", "📝 Attendance Report", "⏳ Live Classes", "👨‍🏫 Leaves", "👟 Shoes", "📢 Notice", "📅 Holidays"])
        
        # --- TAB 1: SUMMARY & MDM REPORT ---
        with tabs[0]: 
            st.subheader(f"MDM Status: {curr_date_str}")
            
            mdm_log = fetch_sheet_data('mdm_log')
            att_log = fetch_sheet_data('student_attendance_master') 
            
            col1, col2 = st.columns([2, 1])
            with col1: view_date = st.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
            with col2: show_all = st.checkbox("Show All History")

            filtered_mdm = mdm_log if show_all else mdm_log[mdm_log['Date'].astype(str) == view_date] if not mdm_log.empty else pd.DataFrame()
            filtered_att = att_log[att_log['Status'] == True] if show_all else att_log[(att_log['Date'].astype(str) == view_date) & (att_log['Status'] == True)] if not att_log.empty else pd.DataFrame()

            c_filter = "All"
            
            if not filtered_mdm.empty or not filtered_att.empty:
                mdm_counts = filtered_mdm.groupby(['Class', 'Section']).size().reset_index(name='MDM Entry') if not filtered_mdm.empty else pd.DataFrame(columns=['Class', 'Section', 'MDM Entry'])
                att_counts = filtered_att.groupby(['Class', 'Section']).size().reset_index(name='Attendance') if not filtered_att.empty else pd.DataFrame(columns=['Class', 'Section', 'Attendance'])

                summary_df = pd.merge(att_counts, mdm_counts, on=['Class', 'Section'], how='outer').fillna(0)
                summary_df['Attendance'], summary_df['MDM Entry'] = summary_df['Attendance'].astype(int), summary_df['MDM Entry'].astype(int)
                summary_df.sort_values(by=['Class', 'Section'], inplace=True)
                
                if not summary_df.empty:
                    summary_df = pd.concat([summary_df, pd.DataFrame([{'Class': 'TOTAL', 'Section': '', 'Attendance': summary_df['Attendance'].sum(), 'MDM Entry': summary_df['MDM Entry'].sum()}])], ignore_index=True)

                st.markdown(f"##### 🏫 Breakdown for {view_date if not show_all else 'All Time'}")
                st.dataframe(summary_df, hide_index=True, use_container_width=True)
                
                st.markdown("##### 📄 Detailed List")
                if not filtered_mdm.empty:
                    filtered_mdm['Class_Sec'] = filtered_mdm['Class'].astype(str) + " " + filtered_mdm['Section'].astype(str)
                    c_filter = st.selectbox("Filter Class", ["All"] + sorted(filtered_mdm['Class_Sec'].unique()))
                    display_df = filtered_mdm[filtered_mdm['Class_Sec'] == c_filter] if c_filter != "All" else filtered_mdm
                        
                    st.dataframe(display_df[['Date', 'Class', 'Section', 'Roll', 'Name']], hide_index=True)
                    st.download_button("📥 Download Report", filtered_mdm.drop(columns=['Class_Sec'], errors='ignore').to_csv(index=False).encode('utf-8'), "MDM_Report.csv", "text/csv")
            else: st.info("No data available for this date.")

            st.divider()
            
            if st.button(f"🗑️ Clear Today's MDM Data for {c_filter}" if c_filter != "All" else "🗑️ Clear Today's MDM Data (All Classes)"):
                temp_mdm = fetch_sheet_data('mdm_log')
                if not temp_mdm.empty:
                    if c_filter == "All": temp_mdm = temp_mdm[temp_mdm['Date'].astype(str) != curr_date_str]
                    else: temp_mdm = temp_mdm[~((temp_mdm['Date'].astype(str) == curr_date_str) & ((temp_mdm['Class'].astype(str) + " " + temp_mdm['Section'].astype(str)) == c_filter))]
                    overwrite_sheet_df('mdm_log', temp_mdm)
                    st.success("MDM Data Cleared from Cloud!")
                    st.rerun()
            
            with st.expander("⚠ Emergency Reset (MDM Database)"):
                if st.button("Reset MDM Database"):
                    overwrite_sheet_df('mdm_log', pd.DataFrame(columns=['Date', 'Teacher', 'Class', 'Section', 'Roll', 'Name', 'Time']))
                    st.success("Database Reset!")
                    st.rerun()

        # --- TAB 2: ATTENDANCE REPORT ---
        with tabs[1]:
            st.subheader("Student Attendance")
            sel_c = st.selectbox("Mark Attendance for Class", ATTENDANCE_OPTIONS, key='ht_att')
            
            if sel_c != "Select Class...":
                t_class, t_sec = sel_c.rsplit(' ', 1)
                std, mdm_log = get_local_csv('students.csv'), fetch_sheet_data('mdm_log')
                
                if not std.empty:
                    if 'Section' not in std.columns: std['Section'] = 'A'
                    ros = std[(std['Class'] == t_class) & (std['Section'] == t_sec)].copy()
                    
                    if not ros.empty:
                        mdm_eaters = mdm_log[(mdm_log['Date'].astype(str) == curr_date_str) & (mdm_log['Class'] == t_class) & (mdm_log['Section'] == t_sec)]['Roll'].astype(str).tolist() if not mdm_log.empty else []
                        
                        ros['Present'], ros['MDM (Ate)'] = True, ros['Roll'].astype(str).isin(mdm_eaters)
                        ed = st.data_editor(ros[['Roll', 'Name', 'Present', 'MDM (Ate)']], hide_index=True, use_container_width=True, disabled=["Roll", "Name", "MDM (Ate)"])
                        
                        c1, c2 = st.columns(2)
                        c1.markdown(f"<div class='att-badge att-neutral'>✅ Total Selected: {ed['Present'].sum()}</div>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='att-badge {'att-done' if mdm_eaters else 'att-wait'}'>MDM Entry: {len(mdm_eaters) if mdm_eaters else 'Wait'}</div>", unsafe_allow_html=True)

                        att_check = fetch_sheet_data('student_attendance_master')
                        is_submitted = not att_check[(att_check['Date'].astype(str) == curr_date_str) & (att_check['Class'] == t_class) & (att_check['Section'] == t_sec)].empty if not att_check.empty else False
                        
                        if is_submitted:
                            st.info(f"🔒 Attendance for {t_class} - {t_sec} is already submitted to Cloud.")
                            if st.button(f"🗑️ Clear Today's Attendance for {t_class} - {t_sec}"):
                                temp_att = att_check[~((att_check['Date'].astype(str) == curr_date_str) & (att_check['Class'] == t_class) & (att_check['Section'] == t_sec))]
                                overwrite_sheet_df('student_attendance_master', temp_att)
                                st.success("Attendance Cleared!")
                                st.rerun()
                        else:
                            if st.button(f"Save Attendance for {t_class} - {t_sec}"):
                                df = pd.DataFrame({'Date': curr_date_str, 'Class': t_class, 'Section': t_sec, 'Roll': ed['Roll'], 'Name': ed['Name'], 'Status': ed['Present']})
                                append_sheet_df('student_attendance_master', df)
                                st.success("✅ Saved to Cloud Database.")
                                st.rerun()

            st.divider()
            
            # --- DAILY ATTENDANCE REPORT ---
            st.subheader("📊 Daily Attendance Report")
            att_log = fetch_sheet_data('student_attendance_master')
            att_view_date = st.date_input("Report Date", datetime.now(), key="att_d").strftime("%d-%m-%Y")
            
            if not att_log.empty:
                target_att = att_log[(att_log['Date'].astype(str) == att_view_date) & (att_log['Status'] == True)]
                if not target_att.empty:
                    pp, i_iv, v = len(target_att[target_att['Class'] == 'CLASS PP']), len(target_att[target_att['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])]), len(target_att[target_att['Class'] == 'CLASS V'])
                    st.markdown(f"""<table class='report-table'><tr><th>Category</th><th>Present</th></tr><tr><td>Class PP</td><td>{pp}</td></tr><tr><td>Class I - IV</td><td>{i_iv}</td></tr><tr><td>Class V</td><td>{v}</td></tr><tr style='font-weight:bold; background:#f0f2f6;'><td>TOTAL</td><td>{pp+i_iv+v}</td></tr></table>""", unsafe_allow_html=True)
                else: st.info(f"No attendance for {att_view_date}.")
            
            # --- MONTHLY ATTENDANCE SUMMARY ---
            st.divider()
            st.subheader("📅 Monthly Attendance Summary")
            with st.expander("Open Monthly View", expanded=False):
                col_m, col_y = st.columns(2)
                months_list = list(calendar.month_name)[1:]
                cur_month_name = calendar.month_name[datetime.now().month]
                selected_month = col_m.selectbox("Select Month", months_list, index=months_list.index(cur_month_name))
                cur_year = datetime.now().year
                selected_year = col_y.selectbox("Select Year", range(cur_year-2, cur_year+3), index=2)
                
                month_idx = months_list.index(selected_month) + 1
                _, days_in_month = calendar.monthrange(selected_year, month_idx)
                
                all_dates = [datetime(selected_year, month_idx, d).strftime("%d-%m-%Y") for d in range(1, days_in_month + 1)]
                all_days = [datetime(selected_year, month_idx, d).strftime("%A") for d in range(1, days_in_month + 1)]
                monthly_df = pd.DataFrame({'Date': all_dates, 'Day_Name': all_days})
                
                present_att = att_log[att_log['Status'] == True].copy() if not att_log.empty else pd.DataFrame(columns=['Date'])
                class_counts = present_att.groupby(['Date', 'Class']).size().unstack(fill_value=0).reset_index() if not present_att.empty else pd.DataFrame(columns=['Date'])
                    
                for cls_name in ['CLASS PP', 'CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'CLASS V']:
                    if cls_name not in class_counts.columns: class_counts[cls_name] = 0
                        
                merged_df = pd.merge(monthly_df, class_counts, on='Date', how='left').fillna(0)
                merged_df['Total (I-IV)'] = merged_df['CLASS I'] + merged_df['CLASS II'] + merged_df['CLASS III'] + merged_df['CLASS IV']
                merged_df = merged_df.rename(columns={'CLASS PP': 'PP', 'CLASS I': 'I', 'CLASS II': 'II', 'CLASS III': 'III', 'CLASS IV': 'IV', 'CLASS V': 'V'})
                
                holidays_csv = get_local_csv('holidays.csv')
                h_dates = holidays_csv['Date'].astype(str).str.strip().tolist() if not holidays_csv.empty else []
                
                def format_row(row):
                    if row['Day_Name'] == 'Sunday': return pd.Series(['Sunday']*7)
                    elif row['Date'] in h_dates: return pd.Series(['Holiday']*7)
                    else: return pd.Series([int(row['PP']), int(row['I']), int(row['II']), int(row['III']), int(row['IV']), int(row['Total (I-IV)']), int(row['V'])])
                
                merged_df[['PP', 'I', 'II', 'III', 'IV', 'Total (I-IV)', 'V']] = merged_df.apply(format_row, axis=1)
                display_m_df = merged_df[['Date', 'PP', 'I', 'II', 'III', 'IV', 'Total (I-IV)', 'V']]
                st.dataframe(display_m_df, hide_index=True, use_container_width=True)
                
                st.download_button("📥 Download Monthly Report", display_m_df.to_csv(index=False).encode('utf-8'), f"Monthly_Attendance_{selected_month}_{selected_year}.csv", "text/csv")
            
            with st.expander("⚠ Emergency Reset"):
                if st.button("Reset Attendance Database"):
                    overwrite_sheet_df('student_attendance_master', pd.DataFrame(columns=['Date', 'Class', 'Section', 'Roll', 'Name', 'Status']))
                    st.rerun()

        # --- TAB 3: LIVE CLASSES ---
        with tabs[2]: 
            st.subheader(f"🏫 School Routine Status: {now.strftime('%A')}")
            routine = get_local_csv('routine.csv')
            today_day = now.strftime('%A')
            
            if not routine.empty:
                today_routine = routine[routine['Day'] == today_day].copy()
                leave_log = fetch_sheet_data('teacher_leave')
                
                if not leave_log.empty and 'Date' in leave_log.columns:
                    for _, l_row in leave_log[leave_log['Date'].astype(str) == curr_date_str].iterrows():
                        absent_code = TEACHER_INITIALS.get(l_row['Teacher'], l_row['Teacher'])
                        for assign in str(l_row.get('Detailed_Sub_Log', '')).split(" | "):
                            if ": " in assign:
                                slot, sub_name = assign.split(": ")
                                sub_code = TEACHER_INITIALS.get(sub_name.strip(), sub_name.strip())
                                today_routine.loc[(today_routine['Teacher'] == absent_code) & (today_routine['Start_Time'].str.strip() == slot.strip()), 'Teacher'] = f"{sub_code} (Sub)"

                today_routine['Start_Obj'] = today_routine['Start_Time'].apply(parse_time_safe)
                today_routine['End_Obj'] = today_routine['End_Time'].apply(parse_time_safe)
                today_routine = today_routine.dropna(subset=['Start_Obj', 'End_Obj']).sort_values('Start_Obj')
                
                st.markdown("### 🔴 LIVE NOW")
                live_classes = [row for _, row in today_routine.iterrows() if row['Start_Obj'] <= curr_time <= row['End_Obj']]
                if live_classes:
                    cols = st.columns(2)
                    for i, r in enumerate(live_classes):
                        is_sub = "(Sub)" in r['Teacher']
                        t_name = f"🔄 {INV_TEACHER_INITIALS.get(r['Teacher'].replace(' (Sub)', ''), r['Teacher'])} (Sub)" if is_sub else f"👨‍🏫 {INV_TEACHER_INITIALS.get(r['Teacher'], r['Teacher'])}"
                        cols[i % 2].markdown(f"""<div class="routine-card" style="border-left: 5px solid {'#ffc107' if is_sub else '#dc3545'};"><h4 style="margin:0; color:#333;">{r['Class']} {r.get('Section', '')}</h4><p style="margin:0; font-weight:bold;">{t_name}</p><p style="margin:0; font-size:12px; color:gray;">{r['Subject']} | Ends: {r['End_Time']}</p></div>""", unsafe_allow_html=True)
                else: st.info("☕ No classes are currently ongoing.")
                
                st.divider()
                st.markdown("### 📅 Full Day Schedule")
                display_routine = today_routine[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject', 'Teacher']].copy()
                display_routine['Teacher'] = display_routine['Teacher'].apply(lambda x: f"🔄 {INV_TEACHER_INITIALS.get(x.replace(' (Sub)', ''), x)} (Sub)" if "(Sub)" in x else INV_TEACHER_INITIALS.get(x, x))
                st.dataframe(display_routine, hide_index=True, use_container_width=True)

        # --- TAB 4: LEAVES ---
        with tabs[3]: 
            st.subheader("Substitution Manager")
            with st.expander("📂 View Cloud Leave Database"): st.dataframe(fetch_sheet_data('teacher_leave'))
            
            sub_date_str = st.date_input("Select Date for Substitutions", datetime.now(), key="sub_date").strftime("%d-%m-%Y")
            target_day = datetime.strptime(sub_date_str, "%d-%m-%Y").strftime('%A')
            abs_t = st.selectbox("Absent Teacher", ["Select..."] + TEACHER_LIST)
            
            if abs_t != "Select...":
                routine = get_local_csv('routine.csv')
                code = TEACHER_INITIALS.get(abs_t, abs_t)
                missed = routine[(routine['Teacher'] == code) & (routine['Day'] == target_day)].copy() if not routine.empty else pd.DataFrame()
                
                leave_log = fetch_sheet_data('teacher_leave')
                existing_leave = leave_log[(leave_log['Date'].astype(str) == sub_date_str) & (leave_log['Teacher'] == abs_t)] if not leave_log.empty else pd.DataFrame()
                
                if not existing_leave.empty:
                    st.success(f"✅ Leave Submitted: **{abs_t}** marked for **{existing_leave.iloc[0]['Type']}** on **{sub_date_str}**.")
                    if st.button("🗑️ Undo / Re-assign Leave"):
                        overwrite_sheet_df('teacher_leave', leave_log.drop(existing_leave.index))
                        st.rerun()
                else:
                    busy_subs = {}
                    if not leave_log.empty:
                        for _, row in leave_log[leave_log['Date'].astype(str) == sub_date_str].iterrows():
                            for assign in str(row.get('Detailed_Sub_Log', '')).split(" | "):
                                if ": " in assign:
                                    slot, sub = assign.split(": ")
                                    if slot not in busy_subs: busy_subs[slot] = []
                                    busy_subs[slot].append(sub.strip())
                                        
                    lt = st.selectbox("Leave Type", ["CL", "SL", "Half Day", "On Duty"])

                    if not missed.empty:
                        assigns = []
                        for idx, row in missed.iterrows():
                            slot = str(row['Start_Time']).strip()
                            busy_codes = routine[(routine['Day'] == target_day) & (routine['Start_Time'] == slot)]['Teacher'].tolist() if not routine.empty else []
                            
                            free_options, busy_options = [], []
                            for t_name in TEACHER_LIST:
                                if t_name == abs_t: continue 
                                t_code = TEACHER_INITIALS.get(t_name, "")
                                if slot in busy_subs and t_name in busy_subs[slot]: busy_options.append(f"⛔ {t_name} (Already Subbing)")
                                elif t_code not in busy_codes: free_options.append(f"✅ {t_name} (Free)")
                                else: busy_options.append(f"⚠️ {t_name} (Busy)")
                            
                            st.markdown(f"<div class='routine-card'><b>{slot}</b> | {row['Class']}</div>", unsafe_allow_html=True)
                            choice = st.selectbox(f"Sub for {slot}", ["Select..."] + free_options + busy_options, key=f"s_{idx}")
                            if choice != "Select...": assigns.append(f"{slot}: {choice.split(' (')[0].replace('✅ ', '').replace('⚠️ ', '').replace('⛔ ', '')}")
                        
                        if st.button("Confirm Substitutes"):
                            append_sheet_df('teacher_leave', pd.DataFrame([{"Date": sub_date_str, "Teacher": abs_t, "Type": lt, "Substitute": "Multiple", "Detailed_Sub_Log": " | ".join(assigns)}]))
                            st.rerun()
                    else:
                        st.info("No classes scheduled for this teacher on this day.")
                        if st.button("Mark Leave (No Sub)"):
                            append_sheet_df('teacher_leave', pd.DataFrame([{"Date": sub_date_str, "Teacher": abs_t, "Type": lt, "Substitute": "None", "Detailed_Sub_Log": "None"}]))
                            st.rerun()

            st.divider()
            st.subheader("📊 Comprehensive Leave Report")
            leave_log = fetch_sheet_data('teacher_leave')
            if not leave_log.empty:
                leave_log['Date_Obj'] = pd.to_datetime(leave_log['Date'], format='%d-%m-%Y', errors='coerce')
                valid_leaves = leave_log.dropna(subset=['Date_Obj']).copy()
                valid_leaves['Period'] = valid_leaves['Date_Obj'].apply(lambda d: 'curr' if d.year == now.year and d.month == now.month else ('prev' if d.year < now.year or (d.year == now.year and d.month < now.month) else 'future'))
                
                rep_teacher = st.selectbox("Select Teacher", ["All Teachers"] + TEACHER_LIST, key="rep_t")
                summary_data = []
                for t in ([rep_teacher] if rep_teacher != "All Teachers" else TEACHER_LIST):
                    t_data = valid_leaves[valid_leaves['Teacher'] == t]
                    p, c = t_data[t_data['Period'] == 'prev'], t_data[t_data['Period'] == 'curr']
                    summary_data.append({'Teacher': t, 'Prev CL': len(p[p['Type'] == 'CL']), 'Prev SL': len(p[p['Type'] == 'SL']), 'Curr CL': len(c[c['Type'] == 'CL']), 'Curr SL': len(c[c['Type'] == 'SL'])})
                    
                st.dataframe(pd.DataFrame(summary_data), hide_index=True, use_container_width=True)
                st.dataframe(valid_leaves if rep_teacher == "All Teachers" else valid_leaves[valid_leaves['Teacher'] == rep_teacher][['Date', 'Teacher', 'Type', 'Substitute']], hide_index=True)

        # --- TAB 5: SHOES ---
        with tabs[4]: 
            s_c = st.selectbox("Class", CLASS_OPTIONS, key='shoe')
            if s_c != "Select Class...":
                std, log = get_local_csv('students.csv'), fetch_sheet_data('shoe_log')
                if not std.empty:
                    ros = std[std['Class'] == s_c].copy()
                    ros['Received'] = ros['Roll'].astype(str).isin(log[log['Class'] == s_c]['Roll'].astype(str).tolist() if not log.empty else [])
                    ros['Mark'], ros['Remark'] = False, ""
                    ed = st.data_editor(ros[['Roll', 'Name', 'Received', 'Mark', 'Remark']], disabled=['Roll','Name','Received'], hide_index=True)
                    if st.button("Save Updates"):
                        new = ed[ed['Mark'] == True]
                        if not new.empty:
                            append_sheet_df('shoe_log', pd.DataFrame({'Roll': new['Roll'], 'Name': new['Name'], 'Class': s_c, 'Received': True, 'Date': curr_date_str, 'Remark': new['Remark']}))
                            st.success("Updated in Cloud!")

        # --- TAB 6: NOTICE ---
        with tabs[5]: 
            n = st.text_area("Notice", get_notice())
            if st.button("Publish to Cloud"):
                publish_notice(n)
                st.success("Published!")
        
        # --- TAB 7: HOLIDAYS ---
        with tabs[6]: 
            st.subheader("🗓️ School Holiday List")
            h_df = get_local_csv('holidays.csv')
            if not h_df.empty: st.data_editor(h_df, num_rows="dynamic", key="h_edit")
            else: st.info("No holiday data uploaded.")
