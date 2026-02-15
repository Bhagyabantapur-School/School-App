import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. PWA & MOBILE APP CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="wide",
    initial_sidebar_state="auto"
)

# Advanced CSS for Mobile App Appearance
st.markdown(
    """
    <head>
        <link rel="manifest" href="./manifest.json">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#007bff">
    </head>
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        .stButton>button {
            width: 100%;
            border-radius: 12px;
            height: 3.5em;
            background-color: #007bff;
            color: white;
            font-weight: bold;
            border: none;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATE & TIME ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

# --- 3. DATA LOADING ---
@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except: return pd.read_csv(file)
    return None

students_df = load_data('students.csv')
routine_df = load_data('routine.csv')
holidays_df = load_data('holidays.csv')

# --- 4. HOLIDAY LOGIC ---
is_holiday = False
holiday_reason = ""
if holidays_df is not None:
    if date_today_str in holidays_df['Date'].values:
        is_holiday = True
        holiday_reason = holidays_df[holidays_df['Date'] == date_today_str]['Occasion'].values[0]
if day_name == "Sunday":
    is_holiday = True
    holiday_reason = "Sunday (Weekly Off)"

# --- 5. TEACHER & ADMIN PASSWORDS ---
ADMIN_PASSWORD = "bpsAPP@2026"
TEACHER_DATA = {
    "TAPASI RANA": {"id": "TR", "pw": "tr26"},
    "SUJATA BISWAS ROTHA": {"id": "SBR", "pw": "sbr26"},
    "ROHINI SINGH": {"id": "RS", "pw": "rs26"},
    "UDAY NARAYAN JANA": {"id": "UNJ", "pw": "unj26"},
    "BIMAL KUMAR PATRA": {"id": "BKP", "pw": "bkp26"},
    "SUSMITA PAUL": {"id": "SP", "pw": "sp26"},
    "TAPAN KUMAR MANDAL": {"id": "TKM", "pw": "tkm26"},
    "MANJUMA KHATUN": {"id": "MK", "pw": "mk26"}
}

if 'sub_map' not in st.session_state:
    st.session_state.sub_map = {} 

# --- 6. SIDEBAR ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.title("🏫 BPS Digital")

st.sidebar.divider()
st.sidebar.write(f"📅 {date_today_str} | {day_name}")

role = st.sidebar.radio("Main Menu:", ["Teacher Login", "Admin Panel", "📅 Holidays"])

# --- 7. APP LOGIC ---

# A. HOLIDAYS
if role == "📅 Holidays":
    st.header("🗓️ School Holidays 2026")
    if holidays_df is not None:
        st.table(holidays_df[['Date', 'Occasion']])

# B. TEACHER LOGIN
elif role == "Teacher Login":
    if is_holiday:
        st.error(f"🚫 School Closed: {holiday_reason}")
        st.stop()
    
    t_name = st.selectbox("Select Your Name", list(TEACHER_DATA.keys()))
    t_pw = st.text_input("Teacher Password", type="password")

    if t_pw == TEACHER_DATA[t_name]["pw"]:
        st.success(f"Verified: {t_name}")
        # (Teacher attendance and MDM code goes here...)
        st.info("Scanner and MDM Checklist Active.")

# C. ADMIN PANEL (NOW SECURED)
elif role == "Admin Panel":
    st.header("🔐 Admin Authentication")
    # Password entry is now in the MAIN area, not just sidebar
    entered_admin_pw = st.text_input("Enter Master Admin Password", type="password")
    
    if entered_admin_pw == ADMIN_PASSWORD:
        st.success("Access Granted. Welcome, Head Teacher.")
        t1, t2, t3 = st.tabs(["Staff Attendance", "Substitution", "System"])
        
        with t1:
            st.subheader("Daily Staff Register")
            df_staff = pd.DataFrame({"Teacher Name": list(TEACHER_DATA.keys()), "Present": True})
            ed_staff = st.data_editor(df_staff, hide_index=True, use_container_width=True)
            if st.button("Save Staff Attendance"):
                ed_staff['Date'] = date_today_str
                ed_staff.to_csv('staff_attendance_log.csv', mode='a', index=False, header=not os.path.exists('staff_attendance_log.csv'))
                st.success("Register Updated Successfully.")
                
        with t2:
            st.subheader("Substitution Manager")
            ab = st.selectbox("Absent Teacher", ["None"] + list(TEACHER_DATA.keys()))
            sb = st.selectbox("Assign To", ["None"] + list(TEACHER_DATA.keys()))
            if st.button("Apply Substitution"):
                st.session_state.sub_map[TEACHER_DATA[ab]["id"]] = TEACHER_DATA[sb]["id"]
                st.success(f"Classes transferred to {sb}")
                
        with t3:
            if st.button("🔄 Reload App Data"):
                st.cache_data.clear()
                st.rerun()
                
    elif entered_admin_pw != "":
        st.error("❌ Incorrect Admin Password. Access Denied.")