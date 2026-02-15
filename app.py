import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. PWA & MOBILE APP HEADERS ---
# This helps Android/Chrome recognize the manifest and look like a native app
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <head>
        <link rel="manifest" href="./manifest.json">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="application-name" content="BPS Digital">
        <meta name="theme-color" content="#007bff">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    </head>
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container { padding-top: 1rem; }
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            background-color: #007bff;
            color: white;
            font-weight: bold;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATE & TIME LOGIC ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

# --- 3. DATA LOADING ---
@st.cache_data
def load_data(file):
    if os.path.exists(file):
        return pd.read_csv(file, encoding='utf-8-sig')
    return None

students_df = load_data('students.csv')
routine_df = load_data('routine.csv')
holidays_df = load_data('holidays.csv')

# --- 4. HOLIDAY & COUNTDOWN CHECK ---
is_holiday = False
holiday_reason = ""
days_until_next = None
next_holiday_name = ""

if holidays_df is not None:
    holidays_df['dt'] = pd.to_datetime(holidays_df['Date'], format='%d-%m-%Y')
    if date_today_str in holidays_df['Date'].values:
        is_holiday = True
        holiday_reason = holidays_df[holidays_df['Date'] == date_today_str]['Occasion'].values[0]
    
    future_holidays = holidays_df[holidays_df['dt'] > date_today_dt].sort_values('dt')
    if not future_holidays.empty:
        next_h = future_holidays.iloc[0]
        days_until_next = (next_h['dt'] - date_today_dt).days + 1
        next_holiday_name = next_h['Occasion']

if day_name == "Sunday":
    is_holiday = True
    holiday_reason = "Sunday (Weekly Off)"

# --- 5. CONFIGURATION ---
SECRET_PASSWORD = "bpsAPP@2026"
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

# --- 6. SIDEBAR DISPLAY ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.title("🏫 BPS Digital")

if os.path.exists('mdm_log.csv'):
    try:
        df_log = pd.read_csv('mdm_log.csv')
        if not df_log.empty:
            last = df_log.iloc[-1]
            st.sidebar.info(f"✅ Last Submit: {last['Time']} ({last['Date']})")
    except: pass

st.sidebar.divider()
st.sidebar.write(f"📅 {date_today_str} | {day_name}")

if days_until_next is not None and not is_holiday:
    st.sidebar.success(f"🎉 {days_until_next} Days to {next_holiday_name}")

role = st.sidebar.radio("Navigation:", ["Teacher Dashboard", "Admin (Head Teacher)", "📅 Holiday List"])

# --- 7. MAIN INTERFACE ---

if role == "📅 Holiday List":
    st.header("🗓️ School Holidays 2026")
    if holidays_df is not None:
        st.table(holidays_df[['Date', 'Occasion']])
    else: st.error("holidays.csv missing")

elif role == "Teacher Dashboard":
    if is_holiday:
        st.error(f"🚫 School Closed: {holiday_reason}")
        st.stop()

    teacher_select = st.selectbox("Select Teacher", list(TEACHER_DATA.keys()))
    pin = st.text_input("Password", type="password")

    if pin == TEACHER_DATA[teacher_select]["pw"]:
        # Staff Attendance Verification
        if os.path.exists('staff_attendance_log.csv'):
            staff_att = pd.read_csv('staff_attendance_log.csv')
            check = staff_att[(staff_att['Date'] == date_today_str) & (staff_att['Teacher Name'] == teacher_select)]
            if not check.empty and not check.iloc[0]['Present']:
                st.error("🚫 You are marked ABSENT today.")
                st.stop()

        st.success(f"Welcome, {teacher_select}")
        
        # Substitution Logic
        my_id = TEACHER_DATA[teacher_select]["id"]
        covering = [my_id]
        for ab, sub in st.session_state.sub_map.items():
            if sub == my_id: covering.append(ab)

        # Class Selection
        my_classes = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'].isin(covering))]
        if not my_classes.empty:
            choice = st.selectbox("Select Class", [f"Class {r['Class']} - {r['Subject']}" for _, r in my_classes.iterrows()])
            sel_class = choice.split(" ")[1]
        else:
            sel_class = st.selectbox("Manual Class Select", ["1", "2", "3", "4", "5"])

        # QR Scanner
        st.subheader("📸 Scan ID")
        qr_id = qrcode_scanner(key='scanner')
        if qr_id:
            found = students_df[students_df['Student Code'].astype(str) == str(qr_id)]
            if not found.empty: st.info(f"✅ Scanned: {found.iloc[0]['Name']}")

        # Attendance Table
        st.divider()
        roster = students_df[students_df['Class'].astype(str) == str(sel_class)].copy()
        if not roster.empty:
            roster['Ate_MDM'] = False
            ed_roster = st.data_editor(roster[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
            
            if st.button("Submit"):
                count = ed_roster['Ate_MDM'].sum()
                t_stamp = datetime.now().strftime("%I:%M %p")
                log = pd.DataFrame([{"Date": date_today_str, "Time": t_stamp, "Class": sel_class, "Count": count, "By": teacher_select}])
                log.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
                st.success("Submitted!")
                st.balloons()
                time.sleep(1)
                st.rerun()

elif role == "Admin (Head Teacher)":
    admin_pin = st.sidebar.text_input("Admin PIN", type="password")
    if admin_pin == SECRET_PASSWORD:
        tab1, tab2, tab3 = st.tabs(["Staff Attendance", "Substitution", "Refresh"])
        with tab1:
            st.header("Daily Staff Register")
            df_staff = pd.DataFrame({"Teacher Name": list(TEACHER_DATA.keys()), "Present": True})
            ed_staff = st.data_editor(df_staff, hide_index=True, use_container_width=True)
            if st.button("Save Staff Attendance"):
                ed_staff['Date'] = date_today_str
                ed_staff.to_csv('staff_attendance_log.csv', mode='a', index=False, header=not os.path.exists('staff_attendance_log.csv'))
                st.success("Saved!")
        with tab2:
            st.header("Arrange Substitution")
            ab = st.selectbox("Absent Teacher", ["None"] + list(TEACHER_DATA.keys()))
            sb = st.selectbox("Substitute Teacher", ["None"] + list(TEACHER_DATA.keys()))
            if st.button("Apply"):
                st.session_state.sub_map[TEACHER_DATA[ab]["id"]] = TEACHER_DATA[sb]["id"]
                st.success("Arrangement Saved")
        with tab3:
            if st.button("Clear Cache & Reload"):
                st.cache_data.clear()
                st.rerun()