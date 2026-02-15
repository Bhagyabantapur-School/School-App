import streamlit as st
import pandas as pd
from datetime import datetime
import os
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. APP CONFIGURATION (PLAY STORE STYLE) ---
st.set_page_config(
    page_title="BPS Digital Manager",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- HIDE STREAMLIT BRANDING (MOBILE APP LOOK) ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container { padding-top: 1rem; padding-bottom: 1rem; }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. DATE & TIME SETUP ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

# --- 3. DATA LOADING ---
@st.cache_data
def load_school_data(file):
    if os.path.exists(file):
        return pd.read_csv(file, encoding='utf-8-sig')
    return None

students_df = load_school_data('students.csv')
routine_df = load_school_data('routine.csv')
holidays_df = load_school_data('holidays.csv')

# --- 4. HOLIDAY & COUNTDOWN LOGIC ---
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

# --- 5. TEACHER & ADMIN CONFIG ---
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

# --- 6. SIDEBAR (LOGO & STATUS) ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.title("🏫 BPS Digital")

# Last Submission Time-stamp
if os.path.exists('mdm_log.csv'):
    df_recent = pd.read_csv('mdm_log.csv')
    if not df_recent.empty:
        last_row = df_recent.iloc[-1]
        st.sidebar.caption(f"✅ Last Submit: {last_row['Time']} ({last_row['Date']})")

st.sidebar.divider()
st.sidebar.write(f"📅 **Date:** {date_today_str}")
st.sidebar.write(f"📖 **Day:** {day_name}")

if days_until_next is not None and not is_holiday:
    st.sidebar.success(f"🎉 **{days_until_next} Days** to {next_holiday_name}!")

role = st.sidebar.radio("Go To:", ["Assistant Teacher (MDM)", "Head Teacher (Admin)", "📅 View Holiday List"])

# --- OPTION: VIEW HOLIDAYS ---
if role == "📅 View Holiday List":
    st.header("🗓️ School Holiday Calendar 2026")
    if holidays_df is not None:
        st.dataframe(holidays_df[['Date', 'Occasion']], use_container_width=True, hide_index=True)
    else:
        st.warning("holidays.csv missing.")

# --- ROLE: ASSISTANT TEACHER ---
elif role == "Assistant Teacher (MDM)":
    if is_holiday:
        st.error(f"🚫 ACCESS RESTRICTED: School is closed for **{holiday_reason}**.")
        st.stop()

    st.header("🍱 Teacher Dashboard")
    selected_teacher = st.selectbox("Select Your Name", list(TEACHER_DATA.keys()))
    entered_pw = st.text_input("Enter Password", type="password")

    if entered_pw == TEACHER_DATA[selected_teacher]["pw"]:
        st.success(f"Welcome, {selected_teacher}!")
        
        # Absent Check
        if os.path.exists('staff_attendance_log.csv'):
            staff_att = pd.read_csv('staff_attendance_log.csv')
            today_rec = staff_att[(staff_att['Date'] == date_today_str) & (staff_att['Teacher Name'] == selected_teacher)]
            if not today_rec.empty and not today_rec.iloc[0]['Present']:
                st.error("🚫 Access Blocked: You are marked as ABSENT today.")
                st.stop()

        # Routine / Substitution
        my_init = TEACHER_DATA[selected_teacher]["id"]
        all_my_inits = [my_init]
        for absent, sub in st.session_state.sub_map.items():
            if sub == my_init: all_my_inits.append(absent)

        active_periods = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'].isin(all_my_inits))]
        if not active_periods.empty:
            options = [f"{r['Class']} - {r['Subject']} ({r['Teacher']})" for _, r in active_periods.iterrows()]
            choice = st.selectbox("Current Period", options)
            selected_row = active_periods.iloc[options.index(choice)]
            sel_class, sel_section = selected_row['Class'], selected_row['Section']
        else:
            st.warning("No scheduled classes.")
            sel_class = st.selectbox("Manual Class", students_df['Class'].unique())
            sel_section = st.selectbox("Manual Section", ["A", "B"])

        # QR Scanner
        scanned_id = qrcode_scanner(key='mdm_scan')
        if scanned_id:
            std = students_df[students_df['Student Code'].astype(str) == str(scanned_id)]
            if not std.empty: st.info(f"✅ Scanned: {std.iloc[0]['Name']}")

        st.divider()
        class_list = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_section)].copy()
        if not class_list.empty:
            class_list['Ate_MDM'] = False
            edited = st.data_editor(class_list[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
            
            if st.button("Submit"):
                total = edited['Ate_MDM'].sum()
                now_time = datetime.now().strftime("%I:%M %p")
                summary = pd.DataFrame([{"Date": date_today_str, "Time": now_time, "Class": sel_class, "Count": total, "By": selected_teacher}])
                summary.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
                st.success(f"Submitted Successfully at {now_time}!")
                st.balloons()
                time.sleep(1)
                st.rerun()
    elif entered_pw != "":
        st.error("❌ Incorrect Password.")

# --- ROLE: HEAD TEACHER (ADMIN) ---
elif role == "Head Teacher (Admin)":
    pw = st.sidebar.text_input("Admin Password", type="password")
    if pw == SECRET_PASSWORD:
        tabs = st.tabs(["👨‍🏫 Staff Attendance", "🔄 Substitution", "📊 Reports", "🔄 System"])
        
        with tabs[0]: 
            st.header(f"👨‍🏫 Staff Register - {date_today_str}")
            teachers = list(TEACHER_DATA.keys())
            t_data = pd.DataFrame({"Teacher Name": teachers, "Present": True})
            edited_t = st.data_editor(t_data, hide_index=True, use_container_width=True, key="t_editor")
            if st.button("Save Official Attendance"):
                staff_log = edited_t.copy()
                staff_log['Date'] = date_today_str
                staff_log['Time_Stamp'] = datetime.now().strftime("%H:%M:%S")
                staff_log.to_csv('staff_attendance_log.csv', mode='a', index=False, header=not os.path.exists('staff_attendance_log.csv'))
                st.success("Attendance saved!")

        with tabs[1]:
            st.header("🔄 Substitution Manager")
            abs_t = st.selectbox("Who is Absent?", ["None"] + list(TEACHER_DATA.keys()))
            sub_t = st.selectbox("Who will take class?", ["None"] + list(TEACHER_MAP.keys()))
            if st.button("Activate"):
                st.session_state.sub_map[TEACHER_DATA[abs_t]["id"]] = TEACHER_DATA[sub_t]["id"]
                st.success("Substituted!")

        with tabs[3]:
            if st.button("🔄 Refresh System"):
                st.cache_data.clear()
                st.rerun()