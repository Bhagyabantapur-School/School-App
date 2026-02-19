import streamlit as st
import pandas as pd
import os
from datetime import datetime, time, timedelta
from streamlit_qrcode_scanner import qrcode_scanner
# Note: FPDF is imported inside the function where needed to avoid issues if not used

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Digital", page_icon="🏫", layout="centered")

# --- SECURITY & WATERMARK CSS ---
# This CSS disables text selection, right-click, and adds a watermark
def inject_security_css(user_name):
    watermark_text = f"{user_name} - CONFIDENTIAL"
    st.markdown(f"""
    <style>
        /* 1. Disable Text Selection */
        body {{
            -webkit-user-select: none; /* Safari */
            -ms-user-select: none; /* IE 10 and IE 11 */
            user-select: none; /* Standard syntax */
        }}
        
        /* 2. Watermark Layer */
        .watermark {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            pointer-events: none; /* Allows clicking through it */
            z-index: 9999;
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><text x="50" y="150" fill="rgba(200, 200, 200, 0.25)" font-size="20" transform="rotate(-45 150 150)" font-family="Arial, sans-serif">{watermark_text}</text></svg>');
            background-repeat: repeat;
        }}

        /* 3. Hide Streamlit Branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        
        [data-testid="stSidebar"] {{display: none;}}
        .block-container {{ padding-top: 1rem; max-width: 650px; }}
        
        /* App Styling */
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
    <script>
    document.addEventListener('contextmenu', event => event.preventDefault());
    </script>
    <div class="watermark"></div>
    """, unsafe_allow_html=True)

# --- 2. USER DATABASE ---
USERS = {
    "admin": {"name": "HEAD TEACHER", "role": "admin", "password": "bpsAPP@2026"},
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
    "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS",
    "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP",
    "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}

TEACHER_LIST = [u["name"] for k, u in USERS.items() if u["role"] == "teacher"]
CLASS_OPTIONS = ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
ATTENDANCE_OPTIONS = [
    "Select Class...", 
    "CLASS PP A", 
    "CLASS I A", 
    "CLASS II A", 
    "CLASS III A", 
    "CLASS IV A", 
    "CLASS IV B", 
    "CLASS V A"
]
CLASS_LOAD = {"CLASS PP": 40, "CLASS I": 35, "CLASS II": 30, "CLASS III": 30, "CLASS IV": 25, "CLASS V": 15}

# --- 3. SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = None

# --- 4. FILE SYSTEM ---
def init_files():
    files_structure = {
        'mdm_log.csv': ['Date', 'Teacher', 'Class', 'Section', 'Roll', 'Name', 'Time'],
        'student_attendance_master.csv': ['Date', 'Class', 'Section', 'Roll', 'Name', 'Status'],
        'shoe_log.csv': ['Roll', 'Name', 'Class', 'Received', 'Date', 'Remark'],
        'teacher_leave.csv': ['Date', 'Teacher', 'Type', 'Substitute', 'Detailed_Sub_Log'],
        'notice.txt': 'Welcome to BPS Digital'
    }
    for f, content in files_structure.items():
        if not os.path.exists(f):
            if f.endswith('.csv'): 
                pd.DataFrame(columns=content).to_csv(f, index=False)
            else: 
                with open(f, 'w') as txt: 
                    txt.write(content)
        elif f.endswith('.csv'):
            try:
                df = pd.read_csv(f)
                if list(df.columns) != content:
                    for c in content:
                        if c not in df.columns:
                            df[c] = 'A' if c == 'Section' else 'None'
                    df = df[content]
                    df.to_csv(f, index=False)
            except: pass
init_files()

# --- 5. TIME HELPERS ---
utc_now = datetime.utcnow()
now = utc_now + timedelta(hours=5, minutes=30)
curr_date_str = now.strftime("%d-%m-%Y")
curr_time = now.time()
MDM_START, MDM_END = time(11, 15), time(12, 30)

def get_csv(file):
    if os.path.exists(file): 
        try: return pd.read_csv(file)
        except: return pd.DataFrame()
    return pd.DataFrame()

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
    
    # Inject basic CSS without watermark for login
    inject_security_css("BPS DIGITAL") 
    
    if os.path.exists('notice.txt'):
        with open('notice.txt', 'r') as f:
            public_notice = f.read()
        if public_notice.strip():
            st.info(f"📢 NOTICE: {public_notice}")

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
        h_df = get_csv('holidays.csv')
        if not h_df.empty: st.table(h_df)
        else: st.info("No data.")

else:
    # --- INJECT SECURITY WITH USER NAME ---
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
        h_df = get_csv('holidays.csv')
        is_h = not h_df[h_df['Date'] == curr_date_str].empty if not h_df.empty else False
        
        if is_h or now.strftime('%A') == 'Sunday':
            st.warning("🏖️ School is closed today.")
        else:
            if os.path.exists('notice.txt'):
                with open('notice.txt', 'r') as f: 
                    n_text = f.read()
                    if n_text.strip(): st.info(f"📢 NOTICE: {n_text}")
            
            at_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leave Status", "📅 Holidays"])

            # --- TAB 1: MDM ENTRY ---
            with at_tabs[0]: 
                mdm_log = get_csv('mdm_log.csv')
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
                    
                    routine = get_csv('routine.csv')
                    my_code = TEACHER_INITIALS.get(t_name_select, t_name_select)
                    today_day = now.strftime('%A')
                    
                    target_class = None
                    target_section = None
                    is_substituting = False
                    absent_teacher_name = ""

                    # 1. Check Substitution
                    leave_log = get_csv('teacher_leave.csv')
                    if not leave_log.empty and 'Date' in leave_log.columns:
                        today_leaves = leave_log[leave_log['Date'] == curr_date_str]
                        for _, row in today_leaves.iterrows():
                            log = str(row.get('Detailed_Sub_Log', ''))
                            if f"11:15: {t_name_select}" in log or f"11:15 AM: {t_name_select}" in log:
                                is_substituting = True
                                absent_teacher_name = row['Teacher']
                                absent_code = TEACHER_INITIALS.get(absent_teacher_name, "")
                                
                                absent_routine = routine[
                                    (routine['Teacher'] == absent_code) & 
                                    (routine['Day'] == today_day)
                                ].copy()
                                absent_routine['Start_Obj'] = absent_routine['Start_Time'].apply(parse_time_safe)
                                match = absent_routine[absent_routine['Start_Obj'] == time(11, 15)]
                                
                                if not match.empty:
                                    r = match.iloc[0]
                                    target_class = r['Class']
                                    target_section = r.get('Section', 'A')
                                break
                    
                    # 2. Check Own Routine
                    if not target_class:
                        my_sched = pd.DataFrame()
                        if not routine.empty and 'Teacher' in routine.columns:
                            my_sched = routine[(routine['Teacher'] == my_code) & (routine['Day'] == today_day)].copy()
                        
                        if not my_sched.empty:
                            my_sched['Start_Obj'] = my_sched['Start_Time'].apply(parse_time_safe)
                            target_rows = my_sched[my_sched['Start_Obj'] == time(11, 15)]
                            if not target_rows.empty:
                                row = target_rows.iloc[0]
                                target_class = row['Class']
                                target_section = row.get('Section', 'A')

                    if target_class:
                        if is_substituting:
                            st.info(f"🔄 **SUBSTITUTION:** You are covering MDM for **{absent_teacher_name}** ({target_class} - {target_section})")
                        else:
                            st.info(f"📌 You are assigned the **11:15 AM** class: **{target_class} - {target_section}**")
                        
                        students = get_csv('students.csv')
                        if not students.empty:
                            if 'Section' not in students.columns: students['Section'] = 'A'
                                
                            roster = students[
                                (students['Class'] == target_class) & 
                                (students['Section'] == target_section)
                            ].copy()
                            
                            if not roster.empty:
                                roster['Ate_MDM'] = False
                                st.write("Mark Students:")
                                qr_val = qrcode_scanner(key='at_qr')
                                edited = st.data_editor(roster[['Section', 'Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
                                
                                marked_count = edited['Ate_MDM'].sum()
                                st.markdown(f"### ✅ Total Selected: {marked_count}")

                                if st.button("Submit MDM"):
                                    ate = edited[edited['Ate_MDM'] == True]
                                    new_rows = []
                                    for _, r in ate.iterrows():
                                        new_rows.append({
                                            'Date': curr_date_str, 
                                            'Teacher': t_name_select, 
                                            'Class': target_class, 
                                            'Section': target_section,
                                            'Roll': r['Roll'], 
                                            'Name': r['Name'], 
                                            'Time': now.strftime("%H:%M")
                                        })
                                    if new_rows:
                                        cols = ['Date', 'Teacher', 'Class', 'Section', 'Roll', 'Name', 'Time']
                                        df_new = pd.DataFrame(new_rows)[cols]
                                        h = not os.path.exists('mdm_log.csv') or os.stat('mdm_log.csv').st_size == 0
                                        df_new.to_csv('mdm_log.csv', mode='a', index=False, header=h)
                                        st.success(f"Submitted {len(new_rows)} students successfully!")
                                        st.rerun()
                                    else: st.warning("No students selected.")
                                
                                att_status_html = ""
                                att_df = get_csv('student_attendance_master.csv')
                                att_count = 0
                                is_att_marked = False
                                
                                if not att_df.empty and 'Date' in att_df.columns:
                                    todays_att = att_df[
                                        (att_df['Date'] == curr_date_str) & 
                                        (att_df['Class'] == target_class) & 
                                        (att_df['Section'] == target_section) &
                                        (att_df['Status'] == True)
                                    ]
                                    if not todays_att.empty:
                                        is_att_marked = True
                                        att_count = len(todays_att)
                                
                                if is_att_marked:
                                    att_status_html = f"<div class='att-badge att-done'>✅ Attendance: {att_count}</div>"
                                else:
                                    att_status_html = "<div class='att-badge att-wait'>⏳ Attendance: Wait</div>"
                                
                                st.markdown(att_status_html, unsafe_allow_html=True)

                            else:
                                st.warning(f"No students found for {target_class} - {target_section}.")
                    else:
                        st.warning(f"⚠️ You do not have a class at 11:15 AM on {today_day}. MDM Entry disabled.")

            with at_tabs[1]: # Routine
                st.subheader("Live Class Status")
                leave_log = get_csv('teacher_leave.csv')
                routine = get_csv('routine.csv')
                
                on_leave = False
                leave_details = None
                if not leave_log.empty and 'Date' in leave_log.columns:
                    my_today_leave = leave_log[
                        (leave_log['Date'] == curr_date_str) & 
                        (leave_log['Teacher'] == t_name_select)
                    ]
                    if not my_today_leave.empty:
                        on_leave = True
                        leave_details = my_today_leave.iloc[0]
                
                if on_leave:
                    st.warning(f"🏖️ You are marked **{leave_details['Type']}** today.")
                    raw_subs = str(leave_details.get('Detailed_Sub_Log', ''))
                    if raw_subs and raw_subs != "None":
                        st.markdown("### 🤝 Substitution Plan")
                        assignments = raw_subs.split(" | ")
                        for assign in assignments:
                            parts = assign.split(": ")
                            if len(parts) == 2:
                                st.markdown(f"<div class='sub-card'><b>{parts[0].strip()}</b> covered by <b>{parts[1].strip()}</b></div>", unsafe_allow_html=True)
                    else:
                        st.info("No specific substitutes assigned yet.")
                        
                else:
                    my_code = TEACHER_INITIALS.get(t_name_select, t_name_select)
                    today_day = now.strftime('%A')
                    
                    my_schedule = pd.DataFrame()
                    if not routine.empty and 'Teacher' in routine.columns:
                        my_schedule = routine[(routine['Teacher'] == my_code) & (routine['Day'] == today_day)].copy()
                        my_schedule['Is_Sub'] = False
                    
                    sub_duties = []
                    if not leave_log.empty:
                        today_absent_records = leave_log[leave_log['Date'] == curr_date_str]
                        for _, row in today_absent_records.iterrows():
                            absent_t = row['Teacher']
                            absent_code = TEACHER_INITIALS.get(absent_t, "")
                            log = str(row['Detailed_Sub_Log'])
                            
                            if t_name_select in log:
                                assignments = log.split(" | ")
                                for assign in assignments:
                                    if f": {t_name_select}" in assign:
                                        parts = assign.split(": ")
                                        if len(parts) == 2:
                                            slot_time = parts[0].strip()
                                            orig_class = routine[
                                                (routine['Teacher'] == absent_code) & 
                                                (routine['Day'] == today_day) & 
                                                (routine['Start_Time'] == slot_time)
                                            ]
                                            if not orig_class.empty:
                                                r = orig_class.iloc[0]
                                                sub_duties.append({
                                                    'Start_Time': r['Start_Time'],
                                                    'End_Time': r['End_Time'],
                                                    'Class': r['Class'],
                                                    'Section': r.get('Section', 'A'),
                                                    'Subject': f"🔄 Sub for {absent_t}",
                                                    'Teacher': my_code,
                                                    'Day': today_day,
                                                    'Is_Sub': True
                                                })
                    
                    if sub_duties:
                        sub_df = pd.DataFrame(sub_duties)
                        my_schedule = pd.concat([my_schedule, sub_df], ignore_index=True)
                    
                    if not my_schedule.empty:
                        my_schedule['Start_Obj'] = my_schedule['Start_Time'].apply(parse_time_safe)
                        my_schedule = my_schedule.dropna(subset=['Start_Obj']).sort_values('Start_Obj')
                        current_class = None
                        next_class = None
                        for _, row in my_schedule.iterrows():
                            s_time = row['Start_Obj']
                            e_time = parse_time_safe(row['End_Time'])
                            if s_time and e_time:
                                if s_time <= curr_time <= e_time: current_class = row
                                elif s_time > curr_time:
                                    next_class = row
                                    break
                        
                        if current_class is not None:
                            sec = current_class.get('Section', '')
                            style = "border-left: 5px solid #ffc107; background-color:#fff3cd;" if current_class['Is_Sub'] else "border-left: 5px solid #28a745;"
                            title_prefix = "🔄 SUB: " if current_class['Is_Sub'] else "🔴 NOW: "
                            html_now = f"""<div class="routine-card" style="{style}"><h3 style="margin:0; color:#333;">{title_prefix}{current_class['Class']} - {sec}</h3><p>{current_class['Subject']}</p><p style="color:gray;">Ends {current_class['End_Time']}</p></div>"""
                            st.markdown(html_now, unsafe_allow_html=True)
                        else: st.info("☕ No class ongoing.")

                        if next_class is not None:
                            try:
                                diff = int((datetime.combine(datetime.today(), next_class['Start_Obj']) - datetime.combine(datetime.today(), curr_time)).total_seconds() / 60)
                                next_style = "background:#fff3cd;" if next_class['Is_Sub'] else "background:#e2e6ea;"
                                next_prefix = "🔄 SUB: " if next_class['Is_Sub'] else "🔜 NEXT: "
                                html_next = f"""<div style="{next_style} padding:10px; border-radius:10px;"><h4 style="margin:0; color:#333;">{next_prefix}{next_class['Class']}</h4><p>Starts in <b>{diff} mins</b></p></div>"""
                                st.markdown(html_next, unsafe_allow_html=True)
                            except: pass
                        
                        st.divider()
                        def highlight_subs(row):
                            return ['background-color: #fff3cd'] * len(row) if row['Subject'].startswith('🔄') else [''] * len(row)
                        st.dataframe(my_schedule[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject']].style.apply(highlight_subs, axis=1), hide_index=True)
                    else: st.info("No classes today.")

            with at_tabs[2]: # Leaves
                st.subheader("My Leave Record")
                leave_log = get_csv('teacher_leave.csv')
                if not leave_log.empty and 'Teacher' in leave_log.columns:
                    my_leaves = leave_log[leave_log['Teacher'] == t_name_select]
                    
                    full_cl = len(my_leaves[my_leaves['Type'] == 'CL'])
                    sl_c = len(my_leaves[my_leaves['Type'] == 'SL'])
                    
                    c1, c2 = st.columns(2)
                    c1.metric("CL Remaining", f"{14 - full_cl}")
                    c2.metric("SL Taken", f"{sl_c}")
                    
                    visible_leaves = my_leaves[~my_leaves['Type'].isin(['Half Day', 'On Duty'])]
                    st.dataframe(visible_leaves[['Date', 'Type', 'Substitute']], hide_index=True)
            
            with at_tabs[3]: # Holidays
                st.subheader("🗓️ School Holiday List")
                h_df = get_csv('holidays.csv')
                if not h_df.empty: st.table(h_df)
                else: st.info("No holiday data available.")

    # ==========================================
    # HEAD TEACHER (ADMIN) DASHBOARD
    # ==========================================
    elif st.session_state.user_role == "admin":
        tabs = st.tabs(["📊 Summary & MDM", "📝 Attendance Report", "👨‍🏫 Leaves", "👟 Shoes", "🆔 Cards", "📢 Notice", "📅 Holidays"])
        
        # --- TAB 1: SUMMARY & MDM REPORT ---
        with tabs[0]: 
            st.subheader(f"MDM Status: {curr_date_str}")
            
            mdm_log = get_csv('mdm_log.csv')
            att_log = get_csv('student_attendance_master.csv') # Load Attendance
            
            col1, col2 = st.columns([2, 1])
            with col1:
                view_date_obj = st.date_input("Select Date", datetime.now())
                view_date = view_date_obj.strftime("%d-%m-%Y")
            with col2:
                show_all = st.checkbox("Show All History")

            if not mdm_log.empty and 'Date' in mdm_log.columns:
                mdm_log['Date'] = mdm_log['Date'].astype(str).str.strip()
                if show_all: filtered_mdm = mdm_log
                else: filtered_mdm = mdm_log[mdm_log['Date'] == view_date]
            else: filtered_mdm = pd.DataFrame()

            if not att_log.empty and 'Date' in att_log.columns:
                att_log['Date'] = att_log['Date'].astype(str).str.strip()
                if show_all: filtered_att = att_log[att_log['Status'] == True]
                else: filtered_att = att_log[(att_log['Date'] == view_date) & (att_log['Status'] == True)]
            else: filtered_att = pd.DataFrame()

            if not filtered_mdm.empty or not filtered_att.empty:
                if not filtered_mdm.empty:
                    if 'Section' not in filtered_mdm.columns: filtered_mdm['Section'] = 'A'
                    mdm_counts = filtered_mdm.groupby(['Class', 'Section']).size().reset_index(name='MDM Entry')
                else:
                    mdm_counts = pd.DataFrame(columns=['Class', 'Section', 'MDM Entry'])

                if not filtered_att.empty:
                    if 'Section' not in filtered_att.columns: filtered_att['Section'] = 'A'
                    att_counts = filtered_att.groupby(['Class', 'Section']).size().reset_index(name='Attendance')
                else:
                    att_counts = pd.DataFrame(columns=['Class', 'Section', 'Attendance'])

                summary_df = pd.merge(att_counts, mdm_counts, on=['Class', 'Section'], how='outer').fillna(0)
                summary_df['Attendance'] = summary_df['Attendance'].astype(int)
                summary_df['MDM Entry'] = summary_df['MDM Entry'].astype(int)
                summary_df.sort_values(by=['Class', 'Section'], inplace=True)

                st.markdown(f"##### 🏫 Breakdown for {view_date if not show_all else 'All Time'}")
                st.dataframe(summary_df, hide_index=True, use_container_width=True)
                
                st.markdown("##### 📄 Detailed List")
                unique_groups = filtered_mdm['Class'].unique() if not filtered_mdm.empty else []
                c_filter = st.selectbox("Filter Class", ["All"] + sorted(unique_groups))
                
                if not filtered_mdm.empty:
                    if c_filter != "All":
                        display_df = filtered_mdm[filtered_mdm['Class'] == c_filter]
                    else:
                        display_df = filtered_mdm
                    st.dataframe(display_df[['Date', 'Class', 'Section', 'Roll', 'Name']], hide_index=True)
                    st.download_button("📥 Download This Report", filtered_mdm.to_csv(index=False).encode('utf-8'), "MDM_Report.csv", "text/csv")
                else:
                    st.warning(f"No MDM entries found for {view_date}.")
            else:
                st.info("No data available for this date.")

            st.divider()
            
            if st.button("🗑️ Clear Today's MDM Data"):
                if not mdm_log.empty and 'Date' in mdm_log.columns:
                    mdm_log = mdm_log[mdm_log['Date'] != curr_date_str]
                    mdm_log.to_csv('mdm_log.csv', index=False)
                    st.success("Today's MDM Data Cleared!")
                    st.rerun()
                else: st.warning("No data to clear.")
            
            with st.expander("⚠ Emergency Reset (MDM Database)"):
                if st.button("Reset MDM Database"):
                    try:
                        os.remove("mdm_log.csv")
                        st.success("Database Reset. Reloading...")
                        st.rerun()
                    except: st.error("Error resetting.")

        # --- TAB 2: ATTENDANCE REPORT ---
        with tabs[1]:
            st.subheader("Student Attendance")
            sel_c = st.selectbox("Mark Attendance for Class", ATTENDANCE_OPTIONS, key='ht_att')
            
            if sel_c != "Select Class...":
                parts = sel_c.rsplit(' ', 1)
                if len(parts) == 2:
                    t_class, t_sec = parts[0], parts[1]
                    
                    std = get_csv('students.csv')
                    mdm_log = get_csv('mdm_log.csv') 
                    
                    if not std.empty:
                        if 'Section' not in std.columns: std['Section'] = 'A'
                        
                        ros = std[(std['Class'] == t_class) & (std['Section'] == t_sec)].copy()
                        
                        if not ros.empty:
                            mdm_eaters = []
                            today_mdm = pd.DataFrame() 
                            if not mdm_log.empty and 'Date' in mdm_log.columns:
                                mdm_log['Date'] = mdm_log['Date'].astype(str).str.strip()
                                today_mdm = mdm_log[
                                    (mdm_log['Date'] == curr_date_str) & 
                                    (mdm_log['Class'] == t_class) & 
                                    (mdm_log['Section'] == t_sec)
                                ]
                                mdm_eaters = today_mdm['Roll'].astype(str).tolist()
                            
                            ros['Present'] = True
                            ros['MDM (Ate)'] = ros['Roll'].astype(str).isin(mdm_eaters)
                            
                            ed = st.data_editor(
                                ros[['Roll', 'Name', 'Present', 'MDM (Ate)']], 
                                hide_index=True, 
                                use_container_width=True,
                                disabled=["Roll", "Name", "MDM (Ate)"]
                            )
                            
                            total_present = ed['Present'].sum()
                            mdm_val = len(today_mdm)
                            mdm_text = f"MDM Entry: {mdm_val}" if not today_mdm.empty else "MDM Entry: Wait"
                            mdm_class = "att-done" if not today_mdm.empty else "att-wait"
                            
                            c1, c2 = st.columns(2)
                            with c1: st.markdown(f"<div class='att-badge att-neutral'>✅ Total Selected: {total_present}</div>", unsafe_allow_html=True)
                            with c2: st.markdown(f"<div class='att-badge {mdm_class}'>{mdm_text}</div>", unsafe_allow_html=True)

                            # --- DUPLICATE CHECK ---
                            att_check = get_csv('student_attendance_master.csv')
                            is_submitted = False
                            if not att_check.empty and 'Date' in att_check.columns:
                                if 'Section' not in att_check.columns: att_check['Section'] = 'A'
                                if not att_check[(att_check['Date'] == curr_date_str) & (att_check['Class'] == t_class) & (att_check['Section'] == t_sec)].empty:
                                    is_submitted = True
                            
                            if is_submitted:
                                st.info(f"🔒 Attendance for {t_class} - {t_sec} is already submitted today.")
                            else:
                                if st.button(f"Save Attendance for {t_class} - {t_sec}"):
                                    rec = ed.copy()
                                    df = pd.DataFrame({
                                        'Date': curr_date_str, 
                                        'Class': t_class, 
                                        'Section': t_sec, 
                                        'Roll': rec['Roll'], 
                                        'Name': rec['Name'], 
                                        'Status': rec['Present']
                                    })
                                    df.to_csv('student_attendance_master.csv', mode='a', index=False, header=False)
                                    st.success("✅ Attendance Submitted for today.")
                                    st.rerun()
                        else:
                            st.warning(f"No students found for {t_class} Section {t_sec}")
                else:
                    st.error("Invalid Class Format selected.")
            
            st.divider()
            
            st.subheader("📊 Daily Attendance Report")
            att_log = get_csv('student_attendance_master.csv')
            att_view_date = st.date_input("Report Date", datetime.now(), key="att_d").strftime("%d-%m-%Y")
            
            if not att_log.empty and 'Status' in att_log.columns:
                target_att = att_log[(att_log['Date'] == att_view_date) & (att_log['Status'] == True)]
                if not target_att.empty:
                    pp_count = target_att[target_att['Class'] == 'CLASS PP'].shape[0]
                    i_iv_count = target_att[target_att['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])].shape[0]
                    v_count = target_att[target_att['Class'] == 'CLASS V'].shape[0]
                    total = pp_count + i_iv_count + v_count
                    
                    tbl_html = f"""<table class='report-table'><tr><th>Category</th><th>Present</th></tr><tr><td>Class PP</td><td>{pp_count}</td></tr><tr><td>Class I - IV</td><td>{i_iv_count}</td></tr><tr><td>Class V</td><td>{v_count}</td></tr><tr style='font-weight:bold; background:#f0f2f6;'><td>TOTAL</td><td>{total}</td></tr></table>"""
                    st.markdown(tbl_html, unsafe_allow_html=True)
                    st.download_button("📥 Download Log", att_log.to_csv(index=False).encode('utf-8'), f"attendance_{att_view_date}.csv", "text/csv")
                else: st.info(f"No attendance for {att_view_date}.")
            else: st.info("Attendance Log empty.")
            
            if st.button("🗑️ Clear Today's Attendance"):
                if not att_log.empty and 'Date' in att_log.columns:
                    att_log['Date'] = att_log['Date'].astype(str).str.strip()
                    att_log = att_log[att_log['Date'] != curr_date_str] 
                    att_log.to_csv('student_attendance_master.csv', index=False)
                    st.success("Today's Attendance Cleared!")
                    st.rerun()
                else: st.warning("No data to clear.")
            
            with st.expander("⚠ Emergency Reset (Attendance Database)"):
                if st.button("Reset Attendance Database"):
                    try:
                        os.remove("student_attendance_master.csv")
                        st.success("Database Reset. Reloading...")
                        st.rerun()
                    except: st.error("Error resetting.")

        # --- TAB 3: LEAVES ---
        with tabs[2]: # Leaves
            st.subheader("Substitution Manager")
            with st.expander("📂 Download Leave Database"):
                live = get_csv('teacher_leave.csv')
                st.dataframe(live)
                st.download_button("Download CSV", live.to_csv(index=False).encode('utf-8'), "leaves.csv", "text/csv")
            
            abs_t = st.selectbox("Absent Teacher", ["Select..."] + TEACHER_LIST)
            if abs_t != "Select...":
                routine = get_csv('routine.csv')
                code = TEACHER_INITIALS.get(abs_t, abs_t)
                day = now.strftime('%A')
                missed = routine[(routine['Teacher'] == code) & (routine['Day'] == day)].copy()
                
                # --- PRE-LOAD TODAY'S SUB ASSIGNMENTS ---
                busy_subs = {}
                leave_log = get_csv('teacher_leave.csv')
                if not leave_log.empty and 'Date' in leave_log.columns:
                    today_leaves = leave_log[leave_log['Date'] == curr_date_str]
                    for _, row in today_leaves.iterrows():
                        raw_log = str(row.get('Detailed_Sub_Log', ''))
                        if raw_log and raw_log != "None":
                            assignments = raw_log.split(" | ")
                            for assignment in assignments:
                                parts = assignment.split(": ")
                                if len(parts) == 2:
                                    t_slot = parts[0].strip()
                                    t_sub_name = parts[1].strip()
                                    if t_slot not in busy_subs: busy_subs[t_slot] = []
                                    busy_subs[t_slot].append(t_sub_name)
                # ----------------------------------------

                if not missed.empty:
                    st.warning(f"{abs_t} has {len(missed)} classes.")
                    assigns = []
                    
                    for idx, row in missed.iterrows():
                        slot = str(row['Start_Time']).strip()
                        
                        busy_at_slot_codes = routine[
                            (routine['Day'] == day) & 
                            (routine['Start_Time'] == slot)
                        ]['Teacher'].tolist()
                        
                        free_options = []
                        busy_options = []
                        
                        for t_name in TEACHER_LIST:
                            if t_name == abs_t: continue 
                            t_code = TEACHER_INITIALS.get(t_name, "")
                            
                            is_already_sub = False
                            if slot in busy_subs and t_name in busy_subs[slot]:
                                is_already_sub = True
                            
                            if is_already_sub:
                                busy_options.append(f"⛔ {t_name} (Already Subbing)")
                            elif t_code not in busy_at_slot_codes:
                                free_options.append(f"✅ {t_name} (Free)")
                            else:
                                busy_info = routine[
                                    (routine['Teacher'] == t_code) & 
                                    (routine['Day'] == day) & 
                                    (routine['Start_Time'] == slot)
                                ]
                                b_class = busy_info.iloc[0]['Class'] if not busy_info.empty else "Class"
                                busy_options.append(f"⚠️ {t_name} (Busy in {b_class})")
                        
                        st.markdown(f"<div class='routine-card'><b>{slot}</b> | {row['Class']}</div>", unsafe_allow_html=True)
                        
                        all_opts = ["Select Substitute..."] + free_options + busy_options
                        choice = st.selectbox(f"Sub for {slot}", all_opts, key=f"s_{idx}")
                        
                        if choice != "Select Substitute...":
                            clean_name = choice.split(" (")[0].replace("✅ ", "").replace("⚠️ ", "").replace("⛔ ", "")
                            assigns.append(f"{slot}: {clean_name}")
                    
                    st.divider()
                    
                    lt = st.selectbox("Leave Type", ["CL", "SL", "Half Day", "On Duty"])
                    
                    if st.button("Confirm"):
                        new = pd.DataFrame([{"Date": curr_date_str, "Teacher": abs_t, "Type": lt, "Substitute": "Multiple", "Detailed_Sub_Log": " | ".join(assigns)}])
                        h = not os.path.exists('teacher_leave.csv') or os.stat('teacher_leave.csv').st_size == 0
                        new.to_csv('teacher_leave.csv', mode='a', index=False, header=h)
                        st.success("Saved! Scroll up to download.")
                else:
                    st.info("No classes today.")
                    if st.button("Mark Absent (No Sub)"):
                         h = not os.path.exists('teacher_leave.csv') or os.stat('teacher_leave.csv').st_size == 0
                         pd.DataFrame([{"Date": curr_date_str, "Teacher": abs_t, "Type": "CL", "Substitute": "None", "Detailed_Sub_Log": "None"}]).to_csv('teacher_leave.csv', mode='a', index=False, header=h)
                         st.success("Saved!")

        with tabs[3]: # Shoes
            s_c = st.selectbox("Class", CLASS_OPTIONS, key='shoe')
            if s_c != "Select Class...":
                std = get_csv('students.csv')
                log = get_csv('shoe_log.csv')
                if not std.empty:
                    ros = std[std['Class'] == s_c].copy()
                    done = log[log['Class'] == s_c]['Roll'].tolist() if not log.empty else []
                    ros['Received'] = ros['Roll'].isin(done)
                    ros['Mark'] = False
                    ros['Remark'] = ""
                    ed = st.data_editor(ros[['Roll', 'Name', 'Received', 'Mark', 'Remark']], disabled=['Roll','Name','Received'], hide_index=True)
                    if st.button("Update"):
                        new = ed[ed['Mark'] == True]
                        if not new.empty:
                            pd.DataFrame({'Roll': new['Roll'], 'Name': new['Name'], 'Class': s_c, 'Received': True, 'Date': curr_date_str, 'Remark': new['Remark']}).to_csv('shoe_log.csv', mode='a', index=False, header=False)
                            st.success("Updated!")

        with tabs[4]: # IDs
            i_c = st.selectbox("Class", CLASS_OPTIONS, key='id')
            if i_c != "Select Class...":
                std = get_csv('students.csv')
                if not std.empty:
                    ros = std[std['Class'] == i_c]
                    sels = st.multiselect("Select", ros['Name'].tolist())
                    if st.button("Download PDF"):
                        pdf = FPDF()
                        for n in sels:
                            r = ros[ros['Name'] == n].iloc[0]
                            pdf.add_page(); pdf.set_font("Arial", 'B', 16)
                            pdf.cell(0, 10, "BPS ID CARD", 0, 1, 'C')
                            pdf.cell(0, 10, f"Name: {r['Name']}", 0, 1)
                            qr = qrcode.make(f"{r['Roll']}-{r['Name']}"); qr.save("q.png")
                            pdf.image("q.png", x=150, y=30, w=40)
                        st.download_button("Download", pdf.output(dest='S').encode('latin-1'), "ids.pdf")

        with tabs[5]: # Notice
            c = ""
            if os.path.exists('notice.txt'):
                with open('notice.txt') as f: c = f.read()
            n = st.text_area("Notice", c)
            if st.button("Publish"):
                with open('notice.txt', 'w') as f: f.write(n)
                st.success("Published!")
        
        with tabs[6]: # Holidays
            st.subheader("🗓️ School Holiday List")
            h_df = get_csv('holidays.csv')
            if not h_df.empty: st.data_editor(h_df, num_rows="dynamic", key="h_edit")
            else: st.info("No holiday data uploaded.")
