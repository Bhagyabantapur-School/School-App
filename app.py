import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
# --- Corrected library import (from requirements.txt) ---
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. INITIAL SETUP ---
st.set_page_config(page_title="Bhagyabantapur PS Manager", layout="wide")
date_today = datetime.now().strftime("%Y-%m-%d")
day_name = datetime.now().strftime('%A')

# Helper to load data from GitHub with Bengali script support
@st.cache_data
def load_school_data(file):
    if os.path.exists(file):
        # 'utf-8-sig' ensures Bengali characters from Google Sheets display correctly
        return pd.read_csv(file, encoding='utf-8-sig')
    return None

students_df = load_school_data('students.csv')
routine_df = load_school_data('routine.csv')

if students_df is None or routine_df is None:
    st.error("⚠️ Error: 'students.csv' or 'routine.csv' missing on GitHub!")
    st.stop()

# --- 2. CONFIGURATION & SUBSTITUTION STATE ---
SECRET_PASSWORD = "bpsAPP@2026"

TEACHER_MAP = {
    "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS",
    "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP",
    "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}

# Persistent state for substitution re-routing
if 'sub_map' not in st.session_state:
    st.session_state.sub_map = {} # Format: {Absent_Initials: Substitute_Initials}

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("🏫 BPS Digital Manager")
role = st.sidebar.radio("Role Select:", ["Assistant Teacher (MDM)", "Head Teacher (Admin)"])

# --- ROLE: ASSISTANT TEACHER ---
if role == "Assistant Teacher (MDM)":
    st.header("🍱 Teacher Dashboard")
    selected_teacher = st.selectbox("Select Your Name", list(TEACHER_MAP.keys()))
    my_init = TEACHER_MAP[selected_teacher]

    # Handle Substitution re-routing
    all_my_inits = [my_init]
    for absent, sub in st.session_state.sub_map.items():
        if sub == my_init:
            all_my_inits.append(absent)
            st.warning(f"🔄 Substitution Mode: You are covering classes for {absent}")

    # Smart Filter: Pulls assigned classes for today from routine.csv
    active_periods = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'].isin(all_my_inits))]
    
    if not active_periods.empty:
        options = [f"{r['Class']} - {r['Subject']} ({r['Teacher']})" for _, r in active_periods.iterrows()]
        choice = st.selectbox("Current Period", options)
        selected_row = active_periods.iloc[options.index(choice)]
        sel_class, sel_section = selected_row['Class'], selected_row['Section']
    else:
        st.warning("No scheduled classes found in routine for today.")
        c1, c2 = st.columns(2)
        sel_class = c1.selectbox("Manual Class", students_df['Class'].unique())
        sel_section = c2.selectbox("Manual Section", ["A", "B"])

    # Hybrid Entry (QR Scanner + Manual Checklist)
    st.subheader("📸 Scan Student ID")
    scanned_id = qrcode_scanner(key='mdm_scan')
    if scanned_id:
        std = students_df[students_df['Student Code'].astype(str) == str(scanned_id)]
        if not std.empty:
            st.info(f"✅ Scanned: {std.iloc[0]['Name']} (Roll: {std.iloc[0]['Roll']})")
        else:
            st.error("ID Code not recognized in student list.")

    st.divider()
    class_list = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_section)].copy()
    if not class_list.empty:
        class_list['Ate_MDM'] = False
        edited = st.data_editor(
            class_list[['Roll', 'Name', 'Ate_MDM']], 
            hide_index=True, 
            use_container_width=True, 
            key=f"mdm_{sel_class}_{sel_section}"
        )
        if st.button("Submit MDM Report"):
            total = edited['Ate_MDM'].sum()
            summary = pd.DataFrame([{"Date": date_today, "Class": sel_class, "Section": sel_section, "Count": total, "By": my_init}])
            summary.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
            st.success(f"Success! {total} MDM entries recorded.")
            st.balloons()

# --- ROLE: HEAD TEACHER (ADMIN) ---
elif role == "Head Teacher (Admin)":
    pw = st.sidebar.text_input("Admin Password", type="password")
    if pw == SECRET_PASSWORD:
        st.sidebar.success("Welcome, Sukhamay Babu!")
        tabs = st.tabs(["👨‍🏫 Staff Attendance", "🔄 Substitution Manager", "📊 Daily Summary", "🔄 Refresh Data"])

        # STAFF ATTENDANCE WITH TIME-STAMPING
        with tabs[0]:
            st.header("👨‍🏫 Teacher Attendance & Time-Stamping")
            teachers = list(TEACHER_MAP.keys())
            t_data = pd.DataFrame({"Teacher Name": teachers, "Present": True})
            edited_t = st.data_editor(t_data, hide_index=True, use_container_width=True, key="t_editor")
            
            if st.button("Save Staff Attendance"):
                stamp = datetime.now().strftime("%H:%M:%S")
                present_staff = edited_t[edited_t['Present'] == True].copy()
                present_staff['Date'] = date_today
                present_staff['Arrival_Time'] = stamp
                
                log_file = 'staff_attendance_log.csv'
                present_staff.to_csv(log_file, mode='a', index=False, header=not os.path.exists(log_file))
                st.success(f"Staff Attendance saved officially at {stamp}!")

        # SUBSTITUTION MODE
        with tabs[1]:
            st.header("🔄 Substitution Manager")
            abs_t = st.selectbox("Absent Teacher", ["None"] + list(TEACHER_MAP.keys()))
            sub_t = st.selectbox("Assign Classes To", ["None"] + list(TEACHER_MAP.keys()))
            if st.button("Activate Substitution"):
                if abs_t != "None" and sub_t != "None":
                    st.session_state.sub_map[TEACHER_MAP[abs_t]] = TEACHER_MAP[sub_t]
                    st.success(f"Substitution Active: {sub_t} will cover {abs_t}")
            if st.button("Clear All Substitutions"):
                st.session_state.sub_map = {}
                st.rerun()

        # DAILY SUMMARY
        with tabs[2]:
            st.header(f"MDM Records for {date_today}")
            if os.path.exists('mdm_log.csv'):
                df_log = pd.read_csv('mdm_log.csv')
                st.dataframe(df_log[df_log['Date'] == date_today], use_container_width=True)

        # SYSTEM REFRESH
        with tabs[3]:
            if st.button("🔄 Reload All CSVs from GitHub"):
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("Please enter the Admin Password to access these tools.")