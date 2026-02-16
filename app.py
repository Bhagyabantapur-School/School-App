import streamlit as st
import pandas as pd
import os
from datetime import datetime, time
import random
from streamlit_qrcode_scanner import qrcode_scanner
from fpdf import FPDF
import base64

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Digital", page_icon="🏫", layout="centered")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        .block-container { padding-top: 1rem; max-width: 700px; }
        .school-title { font-size: 26px !important; font-weight: 900 !important; color: #1a1a1a; margin: 0; line-height: 1.1; }
        .bps-subtext { font-size: 14px; font-weight: 800; color: #007bff; margin-top: -5px; letter-spacing: 1px; }
        .status-box { padding: 10px; border-radius: 10px; border: 1px solid #ddd; background: #f9f9f9; }
        .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA PERSISTENCE & LOADING ---
def load_csv(file):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame()

def save_log(df, file):
    df.to_csv(file, mode='a', index=False, header=not os.path.exists(file))

# State Management
if 'sub_map' not in st.session_state: st.session_state.sub_map = {}
if 'notices' not in st.session_state: st.session_state.notices = "Welcome to BPS Digital."

students_df = load_csv('students.csv')
routine_df = load_csv('routine.csv')
holidays_df = load_csv('holidays.csv')

# Time & Date
now = datetime.now()
curr_time = now.time()
curr_date = now.strftime("%d-%m-%Y")
day_name = now.strftime('%A')
mdm_start, mdm_end = time(11, 15), time(12, 30)

# --- 3. HEADER ---
col_h1, col_h2 = st.columns([1, 4])
with col_h1:
    if os.path.exists("logo.png"): st.image("logo.png", width=80)
    st.markdown('<p class="bps-subtext">BPS Digital</p>', unsafe_allow_html=True)
with col_h2:
    st.markdown('<p class="school-title">Bhagyabantapur<br>Primary School</p>', unsafe_allow_html=True)
st.divider()

# --- 4. HOLIDAY & LEAVE LOGIC ---
is_holiday = False
holiday_msg = ""
if not holidays_df.empty:
    h_row = holidays_df[holidays_df['Date'] == curr_date]
    if not h_row.empty:
        is_holiday = True
        holiday_msg = h_row.iloc[0]['Occasion']
if day_name == "Sunday":
    is_holiday = True
    holiday_msg = "Sunday (Weekly Off)"

# --- 5. NAVIGATION ---
TEACHER_CREDS = {
    "TAPASI RANA": "tr26", "SUJATA BISWAS ROTHA": "sbr26", "ROHINI SINGH": "rs26",
    "UDAY NARAYAN JANA": "unj26", "BIMAL KUMAR PATRA": "bkp26", "SUSMITA PAUL": "sp26",
    "TAPAN KUMAR MANDAL": "tkm26", "MANJUMA KHATUN": "mk26"
}

user_role = st.selectbox("LOGIN AS", ["Assistant Teacher", "Head Teacher", "📅 Holiday List"])

# --- 6. HOLIDAY LIST VIEW ---
if user_role == "📅 Holiday List":
    st.table(holidays_df)

# --- 7. ASSISTANT TEACHER MODULE ---
elif user_role == "Assistant Teacher":
    t_name = st.selectbox("Teacher Name", list(TEACHER_CREDS.keys()))
    t_pw = st.text_input("Password", type="password")
    
    if t_pw == TEACHER_CREDS[t_name]:
        if is_holiday:
            st.warning(f"🏖️ School Closed: {holiday_msg}")
        else:
            # Notice
            st.info(f"📢 Notice: {st.session_state.notices}")
            
            # MDM Logic
            st.subheader("🍱 MDM Entry")
            if not (mdm_start <= curr_time <= mdm_end):
                st.error("⏰ MDM Entry closed (Allowed: 11:15 AM - 12:30 PM)")
            else:
                # Check if already submitted
                mdm_log = load_csv('mdm_log.csv')
                if not mdm_log.empty and len(mdm_log[(mdm_log['Date']==curr_date) & (mdm_log['Teacher']==t_name)]) > 0:
                    st.warning("✅ You have already submitted MDM for today.")
                else:
                    sel_class = st.selectbox("Class", ["PP", "1", "2", "3", "4", "5"])
                    st.write("Scan QR or Check Manual List")
                    # QR Logic
                    qr_val = qrcode_scanner(key='t_qr')
                    
                    class_std = students_df[students_df['Class'].astype(str) == sel_class]
                    class_std['Ate'] = False
                    ed_mdm = st.data_editor(class_std[['Roll', 'Name', 'Ate']], hide_index=True)
                    
                    if st.button("Submit MDM"):
                        log = pd.DataFrame([{"Date": curr_date, "Teacher": t_name, "Class": sel_class, "Count": ed_mdm['Ate'].sum()}])
                        save_log(log, 'mdm_log.csv')
                        st.success("MDM Submitted!")

# --- 8. HEAD TEACHER MODULE ---
elif user_role == "Head Teacher":
    hpw = st.text_input("HT Password", type="password")
    if hpw == "bpsAPP@2026":
        st.success("Welcome, Head Teacher")
        adm_tab = st.tabs(["📊 Summary", "🖋️ Attendance", "🔄 Substitution", "🥿 Shoes", "🆔 ID Cards", "📢 Notice"])
        
        with adm_tab[0]: # Summary
            st.subheader("Attendance Summary")
            att_master = load_csv('student_attendance.csv')
            if not att_master.empty:
                today_att = att_master[att_master['Date'] == curr_date]
                pp = today_att[today_att['Class']=='PP']['Present'].sum()
                i_iv = today_att[today_att['Class'].isin(['1','2','3','4'])]['Present'].sum()
                v = today_att[today_att['Class']=='5']['Present'].sum()
                st.metric("Total PP", pp)
                st.metric("Total I-IV", i_iv)
                st.metric("Total V", v)
        
        with adm_tab[2]: # Substitution
            st.subheader("Substitute Selection")
            absent_t = st.selectbox("Absent Teacher", list(TEACHER_CREDS.keys()))
            sub_t = st.selectbox("Assign to", list(TEACHER_CREDS.keys()))
            if st.button("Apply for Today"):
                st.session_state.sub_map[absent_t] = sub_t
                st.success(f"Classes for {absent_t} moved to {sub_t}")

        with adm_tab[4]: # ID Cards
            st.subheader("Generate ID Cards")
            selected_std = st.multiselect("Select Students", students_df['Name'].tolist())
            if st.button("Generate PDF"):
                # Logic for PDF generation using FPDF would go here
                st.write("Generating PDF for selected students...")

        with adm_tab[5]: # Notice
            st.session_state.notices = st.text_area("Write Notice to Staff", st.session_state.notices)
            st.success("Notice Updated.")
