import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="centered"
)

# Professional CSS for Branding & Summary Cards
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        
        /* BIGGER SCHOOL NAME */
        .school-title {
            font-size: 28px !important;
            font-weight: 800 !important;
            color: #1e1e1e;
            margin: 0;
            line-height: 1.2;
        }

        /* BIGGER SUMMARY TEXT */
        .summary-card {
            background-color: #f8f9fa;
            border: 2px solid #007bff;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0px 6px 12px rgba(0,0,0,0.1);
        }
        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #ddd;
            font-size: 18px; /* Bigger font */
        }
        .summary-val { 
            color: #007bff; 
            font-weight: bold; 
            font-size: 22px; /* Bigger numbers */
        }
        .grand-total-text {
            font-size: 24px;
            font-weight: 900;
            color: #28a745;
        }
        
        .stButton>button {
            width: 100%; border-radius: 12px; height: 4em;
            background-color: #007bff; color: white; font-weight: bold; font-size: 18px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATA LOADING & STATE ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except: return pd.read_csv(file)
    return None

students_df = load_data('students.csv')
holidays_df = load_data('holidays.csv')

TEACHER_CREDS = {
    "TAPASI RANA": {"id": "TR", "pw": "tr26"},
    "SUJATA BISWAS ROTHA": {"id": "SBR", "pw": "sbr26"},
    "ROHINI SINGH": {"id": "RS", "pw": "rs26"},
    "UDAY NARAYAN JANA": {"id": "UNJ", "pw": "unj26"},
    "BIMAL KUMAR PATRA": {"id": "BKP", "pw": "bkp26"},
    "SUSMITA PAUL": {"id": "SP", "pw": "sp26"},
    "TAPAN KUMAR MANDAL": {"id": "TKM", "pw": "tkm26"},
    "MANJUMA KHATUN": {"id": "MK", "pw": "mk26"}
}

# --- 3. HEADER (Logo beside Name) ---
head_col1, head_col2 = st.columns([1, 4])
with head_col1:
    if os.path.exists("logo.png"): 
        st.image("logo.png", width=90) # Slightly bigger logo
    else: 
        st.write("🏫")
with head_col2:
    st.markdown('<p class="school-title">Bhagyabantapur Primary School</p>', unsafe_allow_html=True)

st.markdown(f"<p style='text-align: center; color: gray; font-size: 16px;'>{date_today_str} | {day_name}</p>", unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
page = st.selectbox("SELECT MENU", ["Teacher MDM Entry", "Admin (Attendance & HT Tools)", "📅 View Holiday List"])

# --- 5. TEACHER MDM ENTRY ---
if page == "Teacher MDM Entry":
    t_name = st.selectbox("Select Your Name", list(TEACHER_CREDS.keys()))
    t_pw = st.text_input("Password", type="password")

    if t_pw == TEACHER_CREDS[t_name]["pw"]:
        st.success(f"Verified: {t_name}")
        sel_class = st.selectbox("Class:", ["PP", "1", "2", "3", "4", "5"])
        mdm_count = st.number_input("How many students ate MDM?", min_value=0, max_value=150)
        
        if st.button("SUBMIT MDM COUNT"):
            now_time = datetime.now().strftime("%I:%M %p")
            log = pd.DataFrame([{"Date": date_today_str, "Time": now_time, "Class": sel_class, "Count": mdm_count, "Teacher": t_name}])
            log.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
            st.success("MDM Count Saved!")
            st.balloons()

# --- 6. ADMIN PANEL (HT ATTENDANCE & SUMMARY) ---
elif page == "Admin (Attendance & HT Tools)":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["📊 Attendance Summary", "🖋️ Mark Attendance", "👨‍🏫 Staff Records"])
        
        with tabs[0]:
            st.markdown("### Daily Attendance Overview")
            if os.path.exists('student_attendance_master.csv'):
                att_master = pd.read_csv('student_attendance_master.csv')
                today_att = att_master[att_master['Date'] == date_today_str]
                
                if not today_att.empty:
                    pp_t = today_att[today_att['Class'].astype(str).str.upper() == 'PP']['Present'].sum()
                    i_iv_t = today_att[today_att['Class'].astype(str).isin(['1', '2', '3', '4'])]['Present'].sum()
                    v_t = today_att[today_att['Class'].astype(str) == '5']['Present'].sum()
                    grand = pp_t + i_iv_t + v_t
                    
                    st.markdown(f"""
                    <div class="summary-card">
                        <div class="summary-row"><span>Class PP Total</span><span class="summary-val">{pp_t}</span></div>
                        <div class="summary-row"><span>Class I - IV Total</span><span class="summary-val">{i_iv_t}</span></div>
                        <div class="summary-row"><span>Class V Total</span><span class="summary-val">{v_t}</span></div>
                        <div class="summary-row" style="border:none; margin-top:15px; background-color:#e9fce9; padding:10px; border-radius:8px;">
                            <span class="grand-total-text">GRAND TOTAL</span>
                            <span class="grand-total-text" style="font-size:32px;">{grand}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else: 
                    st.info("No attendance recorded today yet.")
            else: 
                st.info("Records will appear here after marking attendance.")

        with tabs[1]:
            st.subheader("Mark Student Attendance")
            c_target = st.selectbox("Select Class", ["PP", "1", "2", "3", "4", "5"])
            if students_df is not None:
                roster = students_df[students_df['Class'].astype(str) == str(c_target)].copy()
                if not roster.empty:
                    roster['Present'] = True
                    ed_roster = st.data_editor(roster[['Roll', 'Name', 'Present']], hide_index=True, use_container_width=True)
                    if st.button(f"SAVE CLASS {c_target} ATTENDANCE"):
                        final = ed_roster.copy()
                        final['Date'] = date_today_str
                        final['Class'] = c_target
                        final.to_csv('student_attendance_master.csv', mode='a', index=False, header=not os.path.exists('student_attendance_master.csv'))
                        st.success(f"Class {c_target} saved!")
                        time.sleep(1)
                        st.rerun()

# --- 7. HOLIDAY LIST ---
elif page == "📅 View Holiday List":
    st.subheader("School Holiday Calendar 2026")
    if holidays_df is not None: 
        st.table(holidays_df[['Date', 'Occasion']])