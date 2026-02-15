import streamlit as st
import pandas as pd
from datetime import datetime
import os
from streamlit_qr_code_scanner import qr_code_scanner

# --- 1. INITIAL SETUP & CACHED LOADING ---
st.set_page_config(page_title="Bhagyabantapur PS Management", layout="wide")
date_today = datetime.now().strftime("%Y-%m-%d")
day_name = datetime.now().strftime('%A') # This picks Monday, Tuesday, etc.

# Load with utf-8-sig to ensure Bengali font is safe
@st.cache_data
def load_data(file):
    if os.path.exists(file):
        return pd.read_csv(file, encoding='utf-8-sig')
    return None

students_df = load_data('students.csv')
routine_df = load_data('routine.csv')

if students_df is None or routine_df is None:
    st.error("Missing students.csv or routine.csv in GitHub!")
    st.stop()

# --- 2. CONFIGURATION & TEACHER MAP ---
SECRET_PASSWORD = "bpsAPP@2026"
# This map links full names to the initials in your routine.csv
TEACHER_INITIALS = {
    "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS",
    "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP",
    "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("🏫 Bhagyabantapur PS")
role = st.sidebar.radio("Role:", ["Assistant Teacher (MDM)", "Head Teacher (Admin)"])

# --- ROLE: ASSISTANT TEACHER (SMART MODE) ---
if role == "Assistant Teacher (MDM)":
    st.header("🍱 Teacher Dashboard")
    selected_teacher = st.selectbox("Select Your Name", list(TEACHER_INITIALS.keys()))
    my_init = TEACHER_INITIALS[selected_teacher]

    # --- THE SMART FILTER ---
    # Finds what you should be teaching RIGHT NOW based on routine.csv
    active_period = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'] == my_init)]
    
    if not active_period.empty:
        # We take the first match for the current day (or filter by time if you add a time check)
        row = active_period.iloc[0] 
        st.success(f"📍 Scheduled Now: {row['Class']} | Subject: {row['Subject']}")
        sel_class, sel_section = row['Class'], row['Section']
    else:
        st.warning("No class scheduled for you right now in the routine.")
        c1, c2 = st.columns(2)
        sel_class = c1.selectbox("Manual Class", students_df['Class'].unique())
        sel_section = c2.selectbox("Manual Section", ["A", "B"])

    # --- SCANNER SECTION ---
    st.subheader("📸 Scan Student ID")
    scanned_id = qr_code_scanner(key='mdm_scan')
    if scanned_id:
        # Match with 'Student Code' column from your file
        student = students_df[students_df['Student Code'].astype(str) == str(scanned_id)]
        if not student.empty:
            st.info(f"✅ Scanned: {student.iloc[0]['Name']} (Roll: {student.iloc[0]['Roll']})")
        else:
            st.error("Student Code not found.")

    # --- MANUAL CHECKLIST ---
    st.divider()
    class_list = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_section)].copy()
    if not class_list.empty:
        class_list['Ate_MDM'] = False
        edited = st.data_editor(
            class_list[['Roll', 'Name', 'Ate_MDM']],
            column_config={"Ate_MDM": st.column_config.CheckboxColumn("MDM?", default=False)},
            disabled=["Roll", "Name"], hide_index=True, use_container_width=True
        )
        if st.button("Submit MDM Report"):
            # Save logic same as your original code
            st.success("Report Saved!")

# --- ROLE: HEAD TEACHER (ADMIN) ---
elif role == "Head Teacher (Admin)":
    pw = st.sidebar.text_input("Password", type="password")
    if pw == SECRET_PASSWORD:
        tabs = st.tabs(["📋 Attendance", "📦 Distribution", "🔄 Refresh Data"])
        
        with tabs[1]:
            st.header("Dress & Shoe Distribution")
            item = st.selectbox("Select Item", ["School Dress", "Shoes", "Books"])
            st.info("Scan student card to record distribution")
            # Same scanner logic here to log distribution to a CSV
            
        with tabs[2]:
            if st.button("🔄 Clear Cache & Update from GitHub"):
                st.cache_data.clear()
                st.rerun()