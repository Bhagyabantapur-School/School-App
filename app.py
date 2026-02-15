import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS Digital", page_icon="logo.png", layout="centered")

st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        .header-container { display: flex; align-items: center; justify-content: center; gap: 15px; }
        .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; border: none; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATA LOADING & STATE ---
date_today_str = datetime.now().strftime("%d-%m-%Y") 
day_name = datetime.now().strftime('%A')

if 'sub_map' not in st.session_state: st.session_state.sub_map = {}

@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except: return pd.read_csv(file)
    return None

students_df = load_data('students.csv')
routine_df = load_data('routine.csv')
holidays_df = load_data('holidays.csv')

TEACHER_CREDS = {
    "TAPASI RANA": {"id": "TR", "pw": "tr26"}, "SUJATA BISWAS ROTHA": {"id": "SBR", "pw": "sbr26"},
    "ROHINI SINGH": {"id": "RS", "pw": "rs26"}, "UDAY NARAYAN JANA": {"id": "UNJ", "pw": "unj26"},
    "BIMAL KUMAR PATRA": {"id": "BKP", "pw": "bkp26"}, "SUSMITA PAUL": {"id": "SP", "pw": "sp26"},
    "TAPAN KUMAR MANDAL": {"id": "TKM", "pw": "tkm26"}, "MANJUMA KHATUN": {"id": "MK", "pw": "mk26"}
}
rev_mapping = {v['id']: k for k, v in TEACHER_CREDS.items()}

# --- 3. HEADER ---
head_col1, head_col2 = st.columns([1, 4])
with head_col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=70)
with head_col2:
    st.markdown("<h3 style='margin:0; padding-top:10px;'>Bhagyabantapur Primary School</h3>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: gray;'>{date_today_str} | {day_name}</p>", unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
page = st.selectbox("Navigation Menu", ["Teacher Dashboard", "Admin Panel", "📅 View Holiday List"])

# --- 5. PAGES ---

if page == "📅 View Holiday List":
    st.subheader("🗓️ School Holiday Calendar 2026")
    if holidays_df is not None: st.table(holidays_df[['Date', 'Occasion']])
    else: st.error("holidays.csv missing.")

elif page == "Admin Panel":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        # RESTORED: Student Records is now a key Tab
        adm_tabs = st.tabs(["📊 Student Records", "👨‍🏫 Staff Attendance", "🦅 Bird's Eye View", "🔄 Substitution"])
        
        with adm_tabs[0]:
            st.subheader("Student MDM Attendance Records")
            if os.path.exists('mdm_log.csv'):
                all_logs = pd.read_csv('mdm_log.csv')
                # Filter by Class or Date if needed
                st.dataframe(all_logs.iloc[::-1], use_container_width=True, hide_index=True)
                
                # Option to download the report
                csv = all_logs.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Full Attendance Report", data=csv, file_name=f"MDM_Attendance_{date_today_str}.csv", mime='text/csv')
            else:
                st.info("No student attendance data submitted yet today.")

        with adm_tabs[1]:
            st.subheader("Daily Staff Register")
            att_df = pd.DataFrame({"Teacher Name": list(TEACHER_CREDS.keys()), "Present": True})
            ed_att = st.data_editor(att_df, hide_index=True, use_container_width=True)
            if st.button("Save Staff Attendance"):
                ed_att['Date'] = date_today_str
                ed_att.to_csv('staff_attendance_log.csv', mode='a', index=False, header=not os.path.exists('staff_attendance_log.csv'))
                st.success("Staff Attendance Saved.")

        with adm_tabs[2]:
            st.subheader("Live Class Status")
            if routine_df is not None:
                tr = routine_df[routine_df['Day'] == day_name].copy()
                for _, r in tr.iterrows():
                    curr = st.session_state.sub_map.get(r['Teacher'], r['Teacher'])
                    st.info(f"Class {r['Class']}: {rev_mapping.get(curr, curr)}")

        with adm_tabs[3]:
            st.subheader("Manage Substitution")
            abs_t = st.selectbox("Absent Teacher", ["None"] + list(TEACHER_CREDS.keys()))
            sub_t = st.selectbox("Substitute To", ["None"] + list(TEACHER_CREDS.keys()))
            if st.button("Confirm"):
                st.session_state.sub_map[TEACHER_CREDS[abs_t]["id"]] = TEACHER_CREDS[sub_t]["id"]
                st.success("Updated.")

elif page == "Teacher Dashboard":
    # (Teacher login and MDM submission code...)
    st.info("Teacher login active. Select name and enter password to begin.")