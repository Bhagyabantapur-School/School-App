import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. WEB APP CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital Manager",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="wide"
)

# Professional Web Styling
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stButton>button {
                width: 100%;
                border-radius: 8px;
                background-color: #007bff;
                color: white;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. DATE & TIME ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

# --- 3. DATA LOADING ---
@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try:
            return pd.read_csv(file, encoding='utf-8-sig')
        except:
            return pd.read_csv(file)
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

# --- 5. CREDENTIALS ---
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

role = st.sidebar.radio("Navigation:", ["Teacher Dashboard", "Admin Panel", "📅 Holidays"])

# --- 7. APP LOGIC ---

# HOLIDAYS SECTION
if role == "📅 Holidays":
    st.header("🗓️ School Holidays 2026")
    if holidays_df is not None:
        st.table(holidays_df[['Date', 'Occasion']])

# TEACHER DASHBOARD
elif role == "Teacher Dashboard":
    if is_holiday:
        st.error(f"🚫 School Closed: {holiday_reason}")
        st.stop()

    t_name = st.selectbox("Select Your Name", list(TEACHER_DATA.keys()))
    t_pw = st.text_input("Teacher Password", type="password")

    if t_pw == TEACHER_DATA[t_name]["pw"]:
        # Check Attendance Lock
        if os.path.exists('staff_attendance_log.csv'):
            staff = pd.read_csv('staff_attendance_log.csv')
            check = staff[(staff['Date'] == date_today_str) & (staff['Teacher Name'] == t_name)]
            if not check.empty and not check.iloc[0]['Present']:
                st.error("🚫 Access Blocked: You are marked ABSENT today.")
                st.stop()

        st.success(f"Verified: {t_name}")
        
        # Routine & Substitution Logic
        my_id = TEACHER_DATA[t_name]["id"]
        covering = [my_id]
        for ab, sub in st.session_state.sub_map.items():
            if sub == my_id: covering.append(ab)

        classes = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'].isin(covering))]
        if not classes.empty:
            choice = st.selectbox("Select Class", [f"Class {r['Class']} - {r['Subject']}" for _, r in classes.iterrows()])
            sel_class = choice.split(" ")[1]
        else:
            sel_class = st.selectbox("Manual Class Select", ["1", "2", "3", "4", "5"])

        # QR Scanner
        st.subheader("📸 Scan Student ID")
        qr = qrcode_scanner(key='scanner')
        if qr:
            f = students_df[students_df['Student Code'].astype(str) == str(qr)]
            if not f.empty: st.success(f"✅ Scanned: {f.iloc[0]['Name']}")

        # MDM Entry
        st.divider()
        roster = students_df[students_df['Class'].astype(str) == str(sel_class)].copy()
        if not roster.empty:
            roster['Ate_MDM'] = False
            ed = st.data_editor(roster[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
            
            if st.button("Submit"):
                t_stamp = datetime.now().strftime("%I:%M %p")
                log = pd.DataFrame([{"Date": date_today_str, "Time": t_stamp, "Class": sel_class, "Count": ed['Ate_MDM'].sum(), "By": t_name}])
                log.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
                st.success("Submitted!")
                st.balloons()
                time.sleep(1)
                st.rerun()

# SECURED ADMIN PANEL
elif role == "Admin Panel":
    st.header("🔐 Admin Login")
    entered_admin_pw = st.text_input("Enter Admin Password", type="password")
    
    if entered_admin_pw == ADMIN_PASSWORD:
        st.success("Access Granted.")
        t1, t2, t3 = st.tabs(["Staff Attendance", "Substitution", "System"])
        
        with t1:
            st.subheader("Daily Staff Attendance")
            df_s = pd.DataFrame({"Teacher Name": list(TEACHER_DATA.keys()), "Present": True})
            ed_s = st.data_editor(df_s, hide_index=True, use_container_width=True)
            if st.button("Save Register"):
                ed_s['Date'] = date_today_str
                ed_s.to_csv('staff_attendance_log.csv', mode='a', index=False, header=not os.path.exists('staff_attendance_log.csv'))
                st.success("Saved Successfully.")
                
        with t2:
            st.subheader("Substitution Manager")
            ab = st.selectbox("Absent Teacher", ["None"] + list(TEACHER_DATA.keys()))
            sb = st.selectbox("Assign To", ["None"] + list(TEACHER_DATA.keys()))
            if st.button("Transfer Classes"):
                st.session_state.sub_map[TEACHER_DATA[ab]["id"]] = TEACHER_DATA[sb]["id"]
                st.success(f"Classes transferred to {sb}")
                
        with t3:
            if st.button("🔄 Refresh Data"):
                st.cache_data.clear()
                st.rerun()