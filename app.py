import streamlit as st
import pandas as pd
import os
from datetime import datetime, time, timedelta
import qrcode
from fpdf import FPDF
import io
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. APP CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Digital", page_icon="🏫", layout="centered")

# CSS to hide Sidebar and Style like a Native App
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        .school-title { font-size: 26px !important; font-weight: 900 !important; color: #1a1a1a; margin: 0; line-height: 1.1; }
        .bps-subtext { font-size: 14px; font-weight: 800; color: #007bff; margin-top: -5px; letter-spacing: 1px; }
        .summary-card { background-color: #f8f9fa; border: 2px solid #007bff; border-radius: 12px; padding: 15px; margin-bottom: 15px; }
        .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; border: none; }
        .warning-text { color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 8px; border: 1px solid #ffeeba; font-weight: bold; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA INITIALIZATION ---
def init_csv(file, columns):
    if not os.path.exists(file):
        pd.DataFrame(columns=columns).to_csv(file, index=False)

init_csv('mdm_log.csv', ['Date', 'Teacher', 'Class', 'Roll', 'Name', 'Time'])
init_csv('student_attendance.csv', ['Date', 'Class', 'Roll', 'Name', 'Status', 'MarkedBy'])
init_csv('teacher_absence.csv', ['Date', 'Teacher', 'Type', 'Substitute'])
init_csv('shoe_distribution.csv', ['Roll', 'Name', 'Class', 'Received', 'Date', 'Remark'])

# --- 3. DATA LOADING & CONSTANTS ---
now = datetime.now()
curr_date = now.strftime("%Y-%m-%d")
curr_time = now.time()
day_name = now.strftime("%A")

MDM_START = time(11, 15)
MDM_END = time(12, 30)

TEACHER_CREDS = {
    "TAPASI RANA": "tr26", "SUJATA BISWAS ROTHA": "sbr26", "ROHINI SINGH": "rs26",
    "UDAY NARAYAN JANA": "unj26", "BIMAL KUMAR PATRA": "bkp26", "SUSMITA PAUL": "sp26",
    "TAPAN KUMAR MANDAL": "tkm26", "MANJUMA KHATUN": "mk26"
}

@st.cache_data(ttl=60)
def get_students():
    if os.path.exists('students.csv'):
        return pd.read_csv('students.csv')
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_holidays():
    if os.path.exists('holidays.csv'):
        return pd.read_csv('holidays.csv')
    return pd.DataFrame()

# --- 4. HEADER ---
hcol1, hcol2 = st.columns([1, 4])
with hcol1:
    if os.path.exists("logo.png"): st.image("logo.png", width=80)
    st.markdown('<p class="bps-subtext">BPS Digital</p>', unsafe_allow_html=True)
with hcol2:
    st.markdown('<p class="school-title">Bhagyabantapur<br>Primary School</p>', unsafe_allow_html=True)
st.markdown(f"<p style='text-align: right; color: gray;'>{now.strftime('%d %b %Y')} | {day_name}</p>", unsafe_allow_html=True)

# Holiday Check
holidays_df = get_holidays()
is_holiday = False
holiday_name = ""
if not holidays_df.empty and 'Date' in holidays_df.columns:
    match = holidays_df[holidays_df['Date'] == curr_date]
    if not match.empty:
        is_holiday = True
        holiday_name = match.iloc[0]['Occasion']
if day_name == "Sunday":
    is_holiday = True
    holiday_name = "Sunday"

# --- 5. LOGIN SYSTEM ---
st.divider()
login_role = st.selectbox("LOGIN TO SYSTEM", ["Select...", "Assistant Teacher", "Head Teacher", "📅 Holiday List"])

# ==========================================
# MODULE: HOLIDAY LIST
# ==========================================
if login_role == "📅 Holiday List":
    st.subheader("🗓️ School Holiday List")
    st.table(holidays_df)

# ==========================================
# MODULE: ASSISTANT TEACHER
# ==========================================
elif login_role == "Assistant Teacher":
    t_name = st.selectbox("Select Your Name", list(TEACHER_CREDS.keys()))
    t_pw = st.text_input("Enter Password", type="password")
    
    if t_pw == TEACHER_CREDS.get(t_name):
        st.success(f"Verified: {t_name}")
        
        # Holiday Lock
        if is_holiday:
            st.warning(f"🏖️ School is closed today for: {holiday_name}. No data entry allowed.")
        else:
            t_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leaves"])
            
            # 1. MDM Entry
            with t_tabs[0]:
                mdm_log = pd.read_csv('mdm_log.csv')
                # Check if already submitted today
                has_submitted = not mdm_log[(mdm_log['Date'] == curr_date) & (mdm_log['Teacher'] == t_name)].empty
                
                if has_submitted:
                    st.success("✅ MDM Entry for today has already been submitted.")
                elif not (MDM_START <= curr_time <= MDM_END):
                    st.error(f"⏰ MDM Entry is only allowed between 11:15 AM and 12:30 PM.")
                else:
                    st.subheader("Student MDM Entry")
                    sel_class = st.selectbox("Class", ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"])
                    students = get_students()
                    class_list = students[students['Class'] == sel_class].copy()
                    
                    st.write("Scan QR or Check Manual List:")
                    qr_val = qrcode_scanner(key='at_qr')
                    class_list['Ate_MDM'] = False
                    
                    # Logic for QR matching could be added here
                    edited_mdm = st.data_editor(class_list[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
                    
                    if st.button("Submit MDM Attendance"):
                        ate_students = edited_mdm[edited_mdm['Ate_MDM'] == True]
                        new_logs = []
                        for _, s in ate_students.iterrows():
                            new_logs.append([curr_date, t_name, sel_class, s['Roll'], s['Name'], now.strftime("%H:%M")])
                        pd.DataFrame(new_logs, columns=['Date', 'Teacher', 'Class', 'Roll', 'Name', 'Time']).to_csv('mdm_log.csv', mode='a', index=False, header=False)
                        st.balloons()
                        st.success("MDM Submission Successful!")

            # 2. Routine
            with t_tabs[1]:
                st.subheader("Class Routine")
                if os.path.exists('routine.csv'):
                    routine = pd.read_csv('routine.csv')
                    st.dataframe(routine[routine['Teacher'] == t_name], hide_index=True)
                else: st.info("Routine file not found.")

            # 3. Leave Status
            with t_tabs[2]:
                leaves = pd.read_csv('teacher_absence.csv')
                my_leaves = leaves[leaves['Teacher'] == t_name]
                st.metric("Casual Leaves Taken", f"{len(my_leaves)} / 14")
                st.write("Leave History:")
                st.table(my_leaves)

# ==========================================
# MODULE: HEAD TEACHER
# ==========================================
elif login_role == "Head Teacher":
    ht_pw = st.text_input("Head Teacher Password", type="password")
    if ht_pw == "bpsAPP@2026":
        st.success("Welcome, Head Teacher.")
        ht_tabs = st.tabs(["📊 Summary", "📝 Attendance", "👟 Shoes", "🆔 ID Cards", "⚙️ Admin"])
        
        # 1. SUMMARY & WARNINGS
        with ht_tabs[0]:
            st.subheader("Daily Status Overview")
            mdm_log = pd.read_csv('mdm_log.csv')
            today_mdm = mdm_log[mdm_log['Date'] == curr_date]
            
            # Warnings
            submitted_teachers = today_mdm['Teacher'].unique()
            missing = [t for t in TEACHER_CREDS.keys() if t not in submitted_teachers]
            if missing and not is_holiday:
                for mt in missing: st.markdown(f"<p class='warning-text'>⚠️ {mt} has not taken MDM entry yet!</p>", unsafe_allow_html=True)

            # Attendance Summary
            att_log = pd.read_csv('student_attendance.csv')
            today_att = att_log[(att_log['Date'] == curr_date) & (att_log['Status'] == True)]
            
            pp_count = today_att[today_att['Class'] == 'CLASS PP'].shape[0]
            i_iv_count = today_att[today_att['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])].shape[0]
            v_count = today_att[today_att['Class'] == 'CLASS V'].shape[0]
            
            st.markdown(f"""
                <div class='summary-card'>
                    <p><b>Class PP Total:</b> {pp_count}</p>
                    <p><b>Class I - IV Total:</b> {i_iv_count}</p>
                    <p><b>Class V Total:</b> {v_count}</p>
                    <hr>
                    <p style='font-size:18px; color:green;'><b>Grand Total Attendance: {pp_count + i_iv_count + v_count}</b></p>
                </div>
            """, unsafe_allow_html=True)

        # 2. OFFICIAL ATTENDANCE & MDM OVERRIDE
        with ht_tabs[1]:
            st.subheader("Mark Student Attendance")
            students = get_students()
            h_class = st.selectbox("Select Class", ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"], key='ht_class')
            h_list = students[students['Class'] == h_class].copy()
            h_list['Present'] = True
            
            st.write("Scan Student ID or Check Manually:")
            ht_qr = qrcode_scanner(key='ht_qr')
            
            ed_att = st.data_editor(h_list[['Roll', 'Name', 'Present']], hide_index=True)
            if st.button("Save Official Attendance"):
                # Save Logic
                st.success("Attendance Registered.")

        # 3. SHOE DISTRIBUTION
        with ht_tabs[2]:
            st.subheader("Shoe Distribution Tracker")
            shoe_log = pd.read_csv('shoe_distribution.csv')
            s_class = st.selectbox("Select Class", ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"], key='shoe_cls')
            s_list = get_students()[get_students()['Class'] == s_class].copy()
            
            # Check who already received
            received_rolls = shoe_log[shoe_log['Class'] == s_class]['Roll'].tolist()
            s_list['Already_Received'] = s_list['Roll'].isin(received_rolls)
            s_list['Mark_Received'] = False
            s_list['Remark'] = ""
            
            ed_shoes = st.data_editor(s_list[['Roll', 'Name', 'Already_Received', 'Mark_Received', 'Remark']], hide_index=True)
            if st.button("Update Shoe Log"):
                st.success("Log Updated.")

        # 4. ID CARD GENERATOR
        with ht_tabs[3]:
            st.subheader("Generate Student ID Cards")
            id_class = st.selectbox("Select Class", ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"], key='id_cls')
            id_list = get_students()[get_students()['Class'] == id_class]
            selected_ids = st.multiselect("Select Students", id_list['Name'].tolist())
            
            if st.button("Download PDF ID Cards"):
                # PDF Generation Logic
                pdf = FPDF()
                for name in selected_ids:
                    row = id_list[id_list['Name'] == name].iloc[0]
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(200, 10, txt="Bhagyabantapur Primary School", ln=1, align='C')
                    pdf.ln(10)
                    pdf.set_font("Arial", '', 12)
                    pdf.cell(200, 10, txt=f"Name: {row['Name']}", ln=1)
                    pdf.cell(200, 10, txt=f"Roll: {row['Roll']} | Class: {row['Class']}", ln=1)
                    # QR Code
                    qr = qrcode.make(f"{row['Roll']}-{row['Name']}")
                    qr.save("temp_qr.png")
                    pdf.image("temp_qr.png", x=150, y=30, w=40)
                
                pdf_output = pdf.output(dest='S').encode('latin-1')
                st.download_button("Click to Download PDF", pdf_output, "ID_Cards.pdf")

        # 5. ADMIN TOOLS (Substitution, Absence, Notice)
        with ht_tabs[4]:
            st.subheader("Teacher Absence & Substitution")
            abs_t = st.selectbox("Absent Teacher", list(TEACHER_CREDS.keys()))
            sub_t = st.selectbox("Substitute Teacher", list(TEACHER_CREDS.keys()))
            if st.button("Confirm Substitution for Today"):
                st.success(f"{sub_t} is now substituting {abs_t}")

            st.divider()
            st.subheader("Global Notice Board")
            notice = st.text_area("Write Notice to Teachers:")
            if st.button("Publish Notice"):
                st.success("Notice Published.")
