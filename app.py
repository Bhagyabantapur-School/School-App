import streamlit as st
import pandas as pd
import os
from datetime import datetime, time, timedelta
import qrcode
from fpdf import FPDF
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Digital", page_icon="🏫", layout="centered")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 650px; }
        .school-title { font-size: 26px !important; font-weight: 900 !important; color: #1a1a1a; margin: 0; line-height: 1.1; }
        .bps-subtext { font-size: 14px; font-weight: 800; color: #007bff; margin-top: -5px; letter-spacing: 1px; }
        .summary-card { background-color: #ffffff; border: 2px solid #007bff; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); }
        .summary-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f2f6; font-size: 18px; }
        .summary-val { color: #007bff; font-weight: 900; font-size: 22px; }
        .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; border: none; }
        .warning-box { background-color: #fff3cd; color: #856404; padding: 12px; border-radius: 10px; border: 1px solid #ffeeba; margin-bottom: 15px; font-weight: bold; }
        .routine-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #007bff; margin-bottom: 15px; border-right: 1px solid #ddd; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; }
        .tag-leisure { background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-left: 5px; }
        .tag-load { background-color: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-left: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA MAPPINGS & CREDENTIALS ---
TEACHER_INITIALS = {
    "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS",
    "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP",
    "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}

TEACHER_CREDS = {
    "TAPASI RANA": "tr26", "SUJATA BISWAS ROTHA": "sbr26", "ROHINI SINGH": "rs26",
    "UDAY NARAYAN JANA": "unj26", "BIMAL KUMAR PATRA": "bkp26", "SUSMITA PAUL": "sp26",
    "TAPAN KUMAR MANDAL": "tkm26", "MANJUMA KHATUN": "mk26"
}

CLASS_LOAD = {
    "CLASS PP": 40, "CLASS I": 35, "CLASS II": 30, "CLASS III": 30, "CLASS IV": 25, "CLASS V": 15
}

CLASS_OPTIONS = ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]

# --- 3. ROBUST FILE INITIALIZATION ---
def init_files():
    files_structure = {
        'mdm_log.csv': ['Date', 'Teacher', 'Class', 'Roll', 'Name', 'Time'],
        'student_attendance_master.csv': ['Date', 'Class', 'Roll', 'Name', 'Status'],
        'shoe_log.csv': ['Roll', 'Name', 'Class', 'Received', 'Date', 'Remark'],
        'teacher_leave.csv': ['Date', 'Teacher', 'Type', 'Substitute', 'Detailed_Sub_Log'],
        'notice.txt': 'Welcome to BPS Digital'
    }
    for f, content in files_structure.items():
        if not os.path.exists(f):
            if f.endswith('.csv'):
                pd.DataFrame(columns=content).to_csv(f, index=False)
            else:
                with open(f, 'w') as txt: txt.write(content)
        elif f.endswith('.csv'):
            try:
                df = pd.read_csv(f)
                if list(df.columns) != content:
                    if len(df.columns) == len(content):
                        df.columns = content
                        df.to_csv(f, index=False)
                    elif df.empty:
                        pd.DataFrame(columns=content).to_csv(f, index=False)
                    else:
                        for c in content:
                            if c not in df.columns: df[c] = ""
                        df = df[content]
                        df.to_csv(f, index=False)
            except: pass

init_files()

# --- TIMEZONE FIX (IST) & HELPER FUNCTIONS ---
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
    try: return datetime.strptime(str(t_str).strip(), '%H:%M').time()
    except: return None

# --- 4. HEADER ---
hcol1, hcol2 = st.columns([1, 4])
with hcol1:
    if os.path.exists("logo.png"): st.image("logo.png", width=80)
    st.markdown('<p class="bps-subtext">BPS Digital</p>', unsafe_allow_html=True)
with hcol2:
    st.markdown('<p class="school-title">Bhagyabantapur<br>Primary School</p>', unsafe_allow_html=True)
st.divider()

# --- 5. NAVIGATION ---
page = st.selectbox("CHOOSE ACTION", ["Select Action...", "Assistant Teacher Login", "Head Teacher Login", "📅 View Holiday List"])

# ==========================================
# MODULE: HOLIDAY LIST
# ==========================================
if page == "📅 View Holiday List":
    st.subheader("🗓️ School Holiday Calendar")
    h_df = get_csv('holidays.csv')
    if not h_df.empty: st.table(h_df)
    else: st.info("No holiday records uploaded.")

# ==========================================
# MODULE: ASSISTANT TEACHER
# ==========================================
elif page == "Assistant Teacher Login":
    teacher_options = ["Select Your Name..."] + list(TEACHER_CREDS.keys())
    t_name_select = st.selectbox("Teacher Name", teacher_options)
    
    if t_name_select != "Select Your Name...":
        t_pw = st.text_input("Password", type="password")
        
        if t_pw == TEACHER_CREDS.get(t_name_select):
            h_df = get_csv('holidays.csv')
            is_h = not h_df[h_df['Date'] == curr_date_str].empty if not h_df.empty else False
            
            if is_h or now.strftime('%A') == 'Sunday':
                st.warning("🏖️ School is closed today. Data entry is disabled.")
            else:
                if os.path.exists('notice.txt'):
                    with open('notice.txt', 'r') as f: st.info(f"📢 NOTICE: {f.read()}")
                
                at_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leave Status"])

                # --- TAB 1: MDM ENTRY ---
                with at_tabs[0]:
                    mdm_log = get_csv('mdm_log.csv')
                    if 'Date' in mdm_log.columns and 'Teacher' in mdm_log.columns:
                        mdm_log['Date'] = mdm_log['Date'].astype(str).str.strip()
                        mdm_log['Teacher'] = mdm_log['Teacher'].astype(str).str.strip()
                        already_sub = not mdm_log[(mdm_log['Date'] == curr_date_str) & (mdm_log['Teacher'] == t_name_select)].empty
                    else: already_sub = False

                    if already_sub:
                        st.success("✅ You have already submitted MDM for today.")
                    elif not (MDM_START <= curr_time <= MDM_END):
                        st.error("⏰ MDM Entry Closed. Allowed: 11:15 AM - 12:30 PM.")
                    else:
                        st.subheader("Student MDM Entry")
                        sel_class = st.selectbox("Class", CLASS_OPTIONS)
                        
                        if sel_class != "Select Class...":
                            students = get_csv('students.csv')
                            if not students.empty:
                                roster = students[students['Class'] == sel_class].copy()
                                if roster.empty:
                                    st.warning("No students found for this class.")
                                else:
                                    roster['Ate_MDM'] = False
                                    st.write("Scan ID or Check List:")
                                    qr_val = qrcode_scanner(key='at_qr')
                                    edited = st.data_editor(roster[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
                                    
                                    if st.button("Submit MDM Entry"):
                                        ate = edited[edited['Ate_MDM'] == True]
                                        new_rows = []
                                        for _, r in ate.iterrows():
                                            new_rows.append({
                                                'Date': curr_date_str, 'Teacher': t_name_select, 
                                                'Class': sel_class, 'Roll': r['Roll'], 
                                                'Name': r['Name'], 'Time': now.strftime("%H:%M")
                                            })
                                        if new_rows:
                                            is_new = not os.path.exists('mdm_log.csv') or os.stat('mdm_log.csv').st_size == 0
                                            pd.DataFrame(new_rows).to_csv('mdm_log.csv', mode='a', index=False, header=is_new)
                                            st.balloons()
                                            st.success("MDM Submitted Successfully!")
                                        else: st.warning("No students selected.")

                # --- TAB 2: ROUTINE ---
                with at_tabs[1]:
                    st.subheader("Live Class Status")
                    routine = get_csv('routine.csv')
                    if not routine.empty and 'Teacher' in routine.columns:
                        my_code = TEACHER_INITIALS.get(t_name_select, t_name_select)
                        today_day = now.strftime('%A')
                        my_today = routine[(routine['Teacher'] == my_code) & (routine['Day'] == today_day)].copy()
                        
                        if not my_today.empty:
                            my_today['Start_Obj'] = my_today['Start_Time'].apply(parse_time_safe)
                            my_today = my_today.dropna(subset=['Start_Obj']).sort_values('Start_Obj')
                            current_class = None
                            next_class = None
                            for _, row in my_today.iterrows():
                                s_time = row['Start_Obj']
                                e_time = parse_time_safe(row['End_Time'])
                                if s_time and e_time:
                                    if s_time <= curr_time <= e_time: current_class = row
                                    elif s_time > curr_time:
                                        next_class = row
                                        break
                            if current_class is not None:
                                sec = current_class.get('Section', '')
                                st.markdown(f"""
                                <div class="routine-card" style="border-left: 5px solid #28a745;">
                                    <h3 style="margin:0; color:#155724;">🔴 NOW: {current_class['Class']} - {sec}</h3>
                                    <p style="margin:0; font-size:18px;"><b>Subject:</b> {current_class['Subject']}</p>
                                    <p style="margin:0; color:gray;">Ends at {current_class['End_Time']}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            else: st.info("☕ No class ongoing right now.")

                            if next_class is not None:
                                try:
                                    n_dt = datetime.combine(datetime.today(), next_class['Start_Obj'])
                                    c_dt = datetime.combine(datetime.today(), curr_time)
                                    diff_mins = int((n_dt - c_dt).total_seconds() / 60)
                                    sec_next = next_class.get('Section', '')
                                    st.markdown(f"""
                                    <div style="background-color:#fff3cd; padding:15px; border-radius:10px; border-left:5px solid #ffc107; margin-bottom:10px;">
                                        <h4 style="margin:0; color:#856404;">🔜 NEXT: {next_class['Class']} - {sec_next}</h4>
                                        <p>Starts in <b>{diff_mins} mins</b> ({next_class['Start_Time']})</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                except: pass
                            
                            st.divider()
                            st.write("Full Schedule Today:")
                            st.dataframe(my_today[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject']], hide_index=True)
                        else: st.info(f"No classes scheduled for {today_day}.")

                # --- TAB 3: LEAVE STATUS ---
                with at_tabs[2]:
                    st.subheader("My Leave Record")
                    leave_log = get_csv('teacher_leave.csv')
                    if not leave_log.empty and 'Teacher' in leave_log.columns:
                        my_leaves = leave_log[leave_log['Teacher'] == t_name_select]
                        cl_count = len(my_leaves[my_leaves['Type'] == 'CL'])
                        sl_count = len(my_leaves[my_leaves['Type'] == 'SL'])
                        c1, c2 = st.columns(2)
                        c1.metric("CL Remaining", f"{14 - cl_count} / 14")
                        c2.metric("SL (Duty) Taken", f"{sl_count}")
                        st.dataframe(my_leaves[['Date', 'Type', 'Substitute']], hide_index=True)

# ==========================================
# MODULE: HEAD TEACHER (ADMIN)
# ==========================================
elif page == "Head Teacher Login":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["📊 Summary", "📝 Attendance", "👨‍🏫 Leaves & Sub", "👟 Shoes", "🆔 Cards", "📢 Notice"])
        
        # --- TAB 1: SUMMARY ---
        with tabs[0]: 
            st.subheader(f"Status: {curr_date_str}")
            mdm_log = get_csv('mdm_log.csv')
            sub_teachers = []
            if 'Date' in mdm_log.columns and 'Teacher' in mdm_log.columns:
                mdm_log['Date'] = mdm_log['Date'].astype(str).str.strip()
                mdm_log['Teacher'] = mdm_log['Teacher'].astype(str).str.strip()
                today_mdm = mdm_log[mdm_log['Date'] == curr_date_str]
                sub_teachers = today_mdm['Teacher'].unique().tolist()
            
            missing = [t for t in TEACHER_CREDS.keys() if t not in sub_teachers]
            h_df = get_csv('holidays.csv')
            is_h = not h_df[h_df['Date'] == curr_date_str].empty if not h_df.empty else False

            if missing and not is_h and now.strftime('%A') != 'Sunday':
                st.markdown(f"<div class='warning-box'>⚠️ Pending MDM Entry: {', '.join(missing)}</div>", unsafe_allow_html=True)
            elif not missing: st.success("✅ All Teachers Submitted MDM!")

            att_master = get_csv('student_attendance_master.csv')
            if not att_master.empty and 'Status' in att_master.columns:
                today = att_master[att_master['Date'] == curr_date_str]
                today_p = today[today['Status'] == True]
                pp_t = today_p[today_p['Class'] == 'CLASS PP'].shape[0]
                i_iv_t = today_p[today_p['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])].shape[0]
                v_t = today_p[today_p['Class'] == 'CLASS V'].shape[0]
                st.markdown(f"<div class='summary-card'><div class='summary-row'><span>Class PP</span><span class='summary-val'>{pp_t}</span></div><div class='summary-row'><span>Class I - IV</span><span class='summary-val'>{i_iv_t}</span></div><div class='summary-row'><span>Class V</span><span class='summary-val'>{v_t}</span></div><div class='summary-row' style='border:none; margin-top:15px; background-color:#d4edda; padding:10px; border-radius:10px;'><span style='font-weight:900;'>GRAND TOTAL</span><span style='font-size:30px; font-weight:900;'>{pp_t + i_iv_t + v_t}</span></div></div>", unsafe_allow_html=True)
            else: st.info("No attendance marked today.")

        # --- TAB 2: ATTENDANCE ---
        with tabs[1]:
            st.subheader("Mark Student Attendance")
            sel_c = st.selectbox("Class", CLASS_OPTIONS, key='ht_att_c')
            if sel_c != "Select Class...":
                students = get_csv('students.csv')
                if not students.empty:
                    roster = students[students['Class'] == sel_c].copy()
                    if not roster.empty:
                        roster['Present'] = True
                        ed_att = st.data_editor(roster[['Roll', 'Name', 'Present']], hide_index=True, use_container_width=True)
                        if st.button(
