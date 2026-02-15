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

# Professional CSS
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        .stButton>button {
            width: 100%; border-radius: 12px; height: 3.5em;
            background-color: #007bff; color: white; font-weight: bold; border: none;
        }
        .notice-box {
            background-color: #fff3cd; padding: 15px; border-radius: 10px;
            border: 1px solid #ffeeba; color: #856404; margin-bottom: 20px; text-align: center;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATA LOADING ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

# PERSISTENT SUBSTITUTION STATE
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

# Teacher Data Mapping
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

# --- 3. HEADER ---
head_col1, head_col2 = st.columns([1, 4])
with head_col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=70)
with head_col2:
    st.markdown("<h3 style='margin:0; padding-top:10px;'>Bhagyabantapur Primary School</h3>", unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
page = st.selectbox("Navigation Menu", ["Teacher Dashboard", "Admin Panel", "📅 View Holiday List"])

# --- 5. PAGES ---

if page == "📅 View Holiday List":
    st.subheader("🗓️ School Holiday Calendar 2026")
    if holidays_df is not None:
        st.dataframe(holidays_df[['Date', 'Occasion']], use_container_width=True, hide_index=True)
    else:
        st.error("holidays.csv file not found!")

elif page == "Teacher Dashboard":
    # 1. Selection
    selected_teacher = st.selectbox("Select Teacher Name", list(TEACHER_CREDS.keys()))
    entered_pw = st.text_input("Password", type="password")

    # 2. Verification
    if entered_pw == TEACHER_CREDS[selected_teacher]["pw"]:
        st.success(f"Verified! Welcome {selected_teacher}")
        
        # 3. Check Substitution Logic
        my_init = TEACHER_CREDS[selected_teacher]["id"]
        covering_inits = [my_init]
        # Find if HT assigned any other teacher's classes to me
        for absent_init, sub_init in st.session_state.sub_map.items():
            if sub_init == my_init:
                covering_inits.append(absent_init)
        
        # 4. Filter Routine
        if routine_df is not None:
            today_classes = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'].isin(covering_inits))]
            
            if not today_classes.empty:
                class_options = [f"Class {r['Class']} - {r['Subject']} ({r['Teacher']})" for _, r in today_classes.iterrows()]
                selected_class_label = st.selectbox("Select Your Period", class_options)
                
                # Extract Class Number
                target_class = selected_class_label.split(" ")[1]
                
                st.subheader("📸 MDS QR Scanner")
                qr_code = qrcode_scanner(key='teacher_scanner')
                
                # 5. MDM Checklist
                if students_df is not None:
                    roster = students_df[students_df['Class'].astype(str) == str(target_class)].copy()
                    if not roster.empty:
                        roster['Ate_MDM'] = False
                        edited_df = st.data_editor(roster[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
                        
                        if st.button("Submit"):
                            count = edited_df['Ate_MDM'].sum()
                            t_now = datetime.now().strftime("%I:%M %p")
                            log_entry = pd.DataFrame([{"Date": date_today_str, "Time": t_now, "Class": target_class, "Count": count, "By": selected_teacher}])
                            log_entry.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
                            st.success(f"Submitted! Total students fed: {count}")
                            st.balloons()
            else:
                st.warning("No classes scheduled for you today in the routine.")
        else:
            st.error("Routine file missing. Please contact Head Teacher.")
    elif entered_pw != "":
        st.error("Incorrect password.")

elif page == "Admin Panel":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        st.success("Admin Access Granted")
        # Admin Tabs (Bird's Eye, Sub, etc.)
        adm_tabs = st.tabs(["🦅 Bird's Eye View", "🔄 Substitution"])
        with adm_tabs[1]:
            abs_t = st.selectbox("Absent Teacher", ["None"] + list(TEACHER_CREDS.keys()))
            sub_t = st.selectbox("Assign to", ["None"] + list(TEACHER_CREDS.keys()))
            if st.button("Apply"):
                st.session_state.sub_map[TEACHER_CREDS[abs_t]["id"]] = TEACHER_CREDS[sub_t]["id"]
                st.success("Substituted.")