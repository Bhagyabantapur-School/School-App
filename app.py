import streamlit as st
import pandas as pd
import os
from datetime import datetime, time
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
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA INITIALIZATION & LOADING ---
def init_files():
    files = {
        'mdm_log.csv': ['Date', 'Teacher', 'Class', 'Roll', 'Name', 'Time'],
        'student_attendance_master.csv': ['Date', 'Class', 'Roll', 'Name', 'Status'],
        'shoe_log.csv': ['Roll', 'Name', 'Class', 'Received', 'Date', 'Remark'],
        'notice.txt': 'Welcome to BPS Digital'
    }
    for f, cols in files.items():
        if not os.path.exists(f):
            if f.endswith('.csv'): pd.DataFrame(columns=cols).to_csv(f, index=False)
            else: 
                with open(f, 'w') as txt: txt.write(cols)

init_files()

now = datetime.now()
curr_date = now.strftime("%d-%m-%Y")
curr_time = now.time()
MDM_START, MDM_END = time(11, 15), time(12, 30)

TEACHER_CREDS = {
    "TAPASI RANA": "tr26", "SUJATA BISWAS ROTHA": "sbr26", "ROHINI SINGH": "rs26",
    "UDAY NARAYAN JANA": "unj26", "BIMAL KUMAR PATRA": "bkp26", "SUSMITA PAUL": "sp26",
    "TAPAN KUMAR MANDAL": "tkm26", "MANJUMA KHATUN": "mk26"
}

@st.cache_data
def get_csv(file):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame()

# --- 3. BRANDED HEADER ---
hcol1, hcol2 = st.columns([1, 4])
with hcol1:
    if os.path.exists("logo.png"): st.image("logo.png", width=80)
    st.markdown('<p class="bps-subtext">BPS Digital</p>', unsafe_allow_html=True)
with hcol2:
    st.markdown('<p class="school-title">Bhagyabantapur<br>Primary School</p>', unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
page = st.selectbox("CHOOSE ACTION", ["Assistant Teacher MDM Entry", "Admin (Attendance & HT Tools)", "📅 View Holiday List"])

# ==========================================
# MODULE: HOLIDAY LIST
# ==========================================
if page == "📅 View Holiday List":
    st.subheader("🗓️ School Holiday Calendar")
    h_df = get_csv('holidays.csv')
    if not h_df.empty: st.table(h_df)
    else: st.info("No holiday records uploaded.")

# ==========================================
# MODULE: ASSISTANT TEACHER (MDM ENTRY)
# ==========================================
elif page == "Assistant Teacher MDM Entry":
    t_name = st.selectbox("Select Your Name", list(TEACHER_CREDS.keys()))
    t_pw = st.text_input("Password", type="password")
    
    if t_pw == TEACHER_CREDS.get(t_name):
        # Holiday Check
        h_df = get_csv('holidays.csv')
        is_h = not h_df[h_df['Date'] == curr_date].empty if not h_df.empty else False
        
        if is_h or now.strftime('%A') == 'Sunday':
            st.warning("🏖️ School is closed. Data entry is disabled.")
        else:
            # Notice Board
            with open('notice.txt', 'r') as f: st.info(f"📢 NOTICE: {f.read()}")
            
            # MDM Entry Logic
            mdm_log = get_csv('mdm_log.csv')
            if not mdm_log.empty and not mdm_log[(mdm_log['Date']==curr_date) & (mdm_log['Teacher']==t_name)].empty:
                st.success("✅ Your MDM entry for today is already recorded.")
            elif not (MDM_START <= curr_time <= MDM_END):
                st.error(f"⏰ Entry Window: 11:15 AM - 12:30 PM only.")
            else:
                sel_class = st.selectbox("Class", ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"])
                students = get_csv('students.csv')
                if not students.empty:
                    roster = students[students['Class'] == sel_class].copy()
                    roster['Ate_MDM'] = False
                    st.write("Scan ID or Check List:")
                    qr_val = qrcode_scanner(key='at_qr')
                    edited = st.data_editor(roster[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
                    
                    if st.button("Submit MDM Entry"):
                        ate = edited[edited['Ate_MDM'] == True]
                        ate['Date'], ate['Teacher'], ate['Class'], ate['Time'] = curr_date, t_name, sel_class, now.strftime("%H:%M")
                        ate[['Date', 'Teacher', 'Class', 'Roll', 'Name', 'Time']].to_csv('mdm_log.csv', mode='a', index=False, header=False)
                        st.balloons()
                        st.success("MDM Submission Successful!")

# ==========================================
# MODULE: HEAD TEACHER (ADMIN & ATTENDANCE)
# ==========================================
elif page == "Admin (Attendance & HT Tools)":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["📊 Summary", "📝 Student Attendance", "👨‍🏫 Teacher Leaves", "👟 Shoes", "📢 Notice"])
        
        with tabs[0]: # Summary
            st.subheader("Today's Attendance Summary")
            att_master = get_csv('student_attendance_master.csv')
            if not att_master.empty:
                today = att_master[att_master['Date'] == curr_date]
                pp_t = today[today['Class'] == 'CLASS PP']['Status'].sum()
                i_iv_t = today[today['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])]['Status'].sum()
                v_t = today[today['Class'] == 'CLASS V']['Status'].sum()
                
                st.markdown(f"""
                <div class="summary-card">
                    <div class="summary-row"><span>Class PP</span><span class="summary-val">{pp_t}</span></div>
                    <div class="summary-row"><span>Class I - IV</span><span class="summary-val">{i_iv_t}</span></div>
                    <div class="summary-row"><span>Class V</span><span class="summary-val">{v_t}</span></div>
                    <div class="summary-row" style="border:none; margin-top:15px; background-color:#d4edda; padding:10px; border-radius:10px;">
                        <span style="font-weight:900;">GRAND TOTAL</span><span style="font-size:30px; font-weight:900;">{pp_t + i_iv_t + v_t}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else: st.info("No attendance marked yet today.")

        with tabs[1]: # Student Attendance
            st.subheader("Official Student Roll Call")
            sel_c = st.selectbox("Select Class", ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"], key='ht_att')
            students = get_csv('students.csv')
            if not students.empty:
                roster = students[students['Class'] == sel_c].copy()
                roster['Present'] = True
                ed_att = st.data_editor(roster[['Roll', 'Name', 'Present']], hide_index=True, use_container_width=True)
                if st.button(f"Save Class {sel_c} Attendance"):
                    rec = ed_att.copy()
                    rec['Date'], rec['Class'], rec['Status'] = curr_date, sel_c, ed_att['Present']
                    rec[['Date', 'Class', 'Roll', 'Name', 'Status']].to_csv('student_attendance_master.csv', mode='a', index=False, header=False)
                    st.success("Attendance Registered.")

        with tabs[2]: # Teacher Leaves (CL Tracking)
            st.subheader("Teacher Casual Leave Record (Limit: 14)")
            leave_log = get_csv('teacher_leave.csv')
            if not leave_log.empty:
                # Group by teacher to find total leaves taken
                stats = leave_log.groupby('Teacher').size().reset_index(name='Taken')
                stats['Remaining'] = 14 - stats['Taken']
                st.table(stats)
            
            st.divider()
            st.subheader("Mark New Absence")
            abs_t = st.selectbox("Absent Teacher", list(TEACHER_CREDS.keys()))
            if st.button("Confirm Absence for Today"):
                new_l = pd.DataFrame([{"Date": curr_date, "Teacher": abs_t, "Type": "CL", "Substitute": "Internal"}])
                new_l.to_csv('teacher_leave.csv', mode='a', index=False, header=not os.path.exists('teacher_leave.csv'))
                st.success(f"Absence for {abs_t} recorded.")

        with tabs[4]: # Notice
            st.subheader("School Notice Board")
            with open('notice.txt', 'r') as f: old_n = f.read()
            new_n = st.text_area("Update Message:", old_n)
            if st.button("Publish to Staff"):
                with open('notice.txt', 'w') as f: f.write(new_n)
                st.success("Notice updated!")
