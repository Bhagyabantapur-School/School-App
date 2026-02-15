import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
import random
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="centered"
)

# Professional CSS for Branding and Layout
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        
        /* Side-by-side Logo and Name */
        .header-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-bottom: 5px;
        }
        
        .stButton>button {
            width: 100%; border-radius: 12px; height: 3.5em;
            background-color: #007bff; color: white; font-weight: bold; border: none;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATA LOADING & STATE ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

if 'sub_map' not in st.session_state:
    st.session_state.sub_map = {}

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
    "TAPASI RANA": {"id": "TR", "pw": "tr26"},
    "SUJATA BISWAS ROTHA": {"id": "SBR", "pw": "sbr26"},
    "ROHINI SINGH": {"id": "RS", "pw": "rs26"},
    "UDAY NARAYAN JANA": {"id": "UNJ", "pw": "unj26"},
    "BIMAL KUMAR PATRA": {"id": "BKP", "pw": "bkp26"},
    "SUSMITA PAUL": {"id": "SP", "pw": "sp26"},
    "TAPAN KUMAR MANDAL": {"id": "TKM", "pw": "tkm26"},
    "MANJUMA KHATUN": {"id": "MK", "pw": "mk26"}
}
rev_mapping = {v['id']: k for k, v in TEACHER_CREDS.items()}

# --- 3. HEADER (Logo beside School Name) ---
head_col1, head_col2 = st.columns([1, 4])
with head_col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=70)
with head_col2:
    st.markdown("<h3 style='margin:0; padding-top:10px;'>Bhagyabantapur Primary School</h3>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: gray;'>{date_today_str} | {day_name}</p>", unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
# Restored "Holiday List" to the main menu
page = st.selectbox("Navigation Menu", ["Teacher Dashboard", "Admin Panel", "📅 View Holiday List"])

# --- 5. PAGES ---

# A. HOLIDAY LIST (RESTORED)
if page == "📅 View Holiday List":
    st.subheader("🗓️ School Holiday Calendar 2026")
    if holidays_df is not None:
        # Display as a clean, simple table
        st.table(holidays_df[['Date', 'Occasion']])
    else:
        st.error("Error: 'holidays.csv' not found in your GitHub folder.")

# B. ADMIN PANEL
elif page == "Admin Panel":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        adm_tabs = st.tabs(["👨‍🏫 Staff Attendance", "🦅 Bird's Eye View", "🔄 Substitution"])
        
        with adm_tabs[0]:
            st.subheader(f"Staff Attendance - {date_today_str}")
            att_df = pd.DataFrame({"Teacher Name": list(TEACHER_CREDS.keys()), "Present": True})
            edited_att = st.data_editor(att_df, hide_index=True, use_container_width=True)
            if st.button("Save Official Attendance"):
                final_att = edited_att.copy()
                final_att['Date'] = date_today_str
                final_att.to_csv('staff_attendance_log.csv', mode='a', index=False, header=not os.path.exists('staff_attendance_log.csv'))
                st.success("Attendance Saved.")

        with adm_tabs[1]:
            st.subheader("📍 Real-time School Status")
            if routine_df is not None:
                today_routine = routine_df[routine_df['Day'] == day_name].copy()
                for _, row in today_routine.iterrows():
                    orig = row['Teacher']
                    curr = st.session_state.sub_map.get(orig, orig)
                    st.info(f"**Class {row['Class']}**: {rev_mapping.get(curr, curr)} (Sub: {orig != curr})")

        with adm_tabs[2]:
            st.subheader("Manage Substitution")
            abs_t = st.selectbox("Absent Teacher", ["None"] + list(TEACHER_CREDS.keys()))
            sub_t = st.selectbox("Substitute To", ["None"] + list(TEACHER_CREDS.keys()))
            if st.button("Apply"):
                st.session_state.sub_map[TEACHER_CREDS[abs_t]["id"]] = TEACHER_CREDS[sub_t]["id"]
                st.success("Done.")

# C. TEACHER DASHBOARD
elif page == "Teacher Dashboard":
    selected_teacher = st.selectbox("Teacher Name", list(TEACHER_CREDS.keys()))
    entered_pw = st.text_input("Password", type="password")

    if entered_pw == TEACHER_CREDS[selected_teacher]["pw"]:
        # Block if absent
        if os.path.exists('staff_attendance_log.csv'):
            log = pd.read_csv('staff_attendance_log.csv')
            today_rec = log[(log['Date'] == date_today_str) & (log['Teacher Name'] == selected_teacher)]
            if not today_rec.empty and today_rec.iloc[-1]['Present'] == False:
                st.error("🚫 Access Blocked: You are marked ABSENT today.")
                st.stop()

        st.success(f"Welcome {selected_teacher}!")
        # (MDM / QR logic follows here...)