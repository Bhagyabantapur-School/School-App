import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
# --- CORRECTED IMPORT ---
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. INITIAL SETUP ---
st.set_page_config(page_title="Bhagyabantapur PS Manager", layout="wide")
date_today = datetime.now().strftime("%Y-%m-%d")
day_name = datetime.now().strftime('%A')

# Helper to load CSVs with Bengali Font support
@st.cache_data
def load_school_data(file):
    if os.path.exists(file):
        # utf-8-sig ensures Bengali characters from Google Sheets display correctly
        return pd.read_csv(file, encoding='utf-8-sig')
    return None

students_df = load_school_data('students.csv')
routine_df = load_school_data('routine.csv')

if students_df is None or routine_df is None:
    st.error("⚠️ Error: 'students.csv' or 'routine.csv' not found on GitHub!")
    st.stop()

# --- 2. CONFIGURATION ---
SECRET_PASSWORD = "bpsAPP@2026"

# Map Full Names to Routine Initials
TEACHER_MAP = {
    "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS",
    "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP",
    "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("🏫 BPS Digital Manager")
role = st.sidebar.radio("Apna Role Chunnein:", ["Assistant Teacher (MDM)", "Head Teacher (Admin)"])

# --- ROLE: ASSISTANT TEACHER (SMART MODE) ---
if role == "Assistant Teacher (MDM)":
    st.header("🍱 Teacher Dashboard")
    selected_teacher = st.selectbox("Apna Naam Chunnein", list(TEACHER_MAP.keys()))
    my_init = TEACHER_MAP[selected_teacher]

    # --- THE SMART FILTER ---
    # Finds active class based on current day and teacher initials
    active_period = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'] == my_init)]
    
    if not active_period.empty:
        row = active_period.iloc[0] 
        st.success(f"📍 Scheduled Now: {row['Class']} | Subject: {row['Subject']}")
        sel_class, sel_section = row['Class'], row['Section']
    else:
        st.warning(f"No classes scheduled for {selected_teacher} on {day_name}.")
        c1, c2 = st.columns(2)
        sel_class = c1.selectbox("Manual Class", students_df['Class'].unique())
        sel_section = c2.selectbox("Manual Section", ["A", "B"])

    # --- HYBRID ENTRY: SCANNER + CHECKLIST ---
    st.subheader("📸 Scan Student ID")
    # Corrected function call
    scanned_id = qrcode_scanner(key='mdm_scan')
    
    if scanned_id:
        # Match with 'Student Code' column (13 digits)
        std = students_df[students_df['Student Code'].astype(str) == str(scanned_id)]
        if not std.empty:
            st.info(f"✅ Scanned: {std.iloc[0]['Name']} (Roll: {std.iloc[0]['Roll']})")
        else:
            st.error("Student Code mismatch.")

    st.divider()
    
    # Filter student list for display
    class_list = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_section)].copy()
    
    if not class_list.empty:
        class_list['Ate_MDM'] = False
        
        edited_mdm = st.data_editor(
            class_list[['Roll', 'Name', 'Ate_MDM']],
            column_config={"Ate_MDM": st.column_config.CheckboxColumn("MDM Liya?", default=False)},
            disabled=["Roll", "Name"],
            hide_index=True,
            use_container_width=True,
            key=f"editor_{sel_class}_{sel_section}"
        )
        
        total = edited_mdm['Ate_MDM'].sum()
        st.metric("Total MDM Count", total)

        if st.button("Submit Daily MDM Report"):
            summary = pd.DataFrame([{
                "Date": date_today, "Class": sel_class, "Section": sel_section, 
                "Count": total, "Teacher": my_init
            }])
            summary.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
            st.success("MDM Report Submitted Successfully!")
            st.balloons()

# --- ROLE: HEAD TEACHER (ADMIN) ---
elif role == "Head Teacher (Admin)":
    pw_input = st.sidebar.text_input("Admin Password", type="password")
    
    if pw_input == SECRET_PASSWORD:
        st.sidebar.success("Welcome, Sukhamay Babu!")
        tabs = st.tabs(["📊 Daily Reports", "📦 Distribution", "🔄 System Refresh"])

        with tabs[0]:
            st.header("School Reporting Summary")
            if os.path.exists('mdm_log.csv'):
                df_log = pd.read_csv('mdm_log.csv')
                st.write(f"### Records for {date_today}")
                st.dataframe(df_log[df_log['Date'] == date_today], use_container_width=True)

        with tabs[1]:
            st.header("Dress & Shoe Distribution")
            item = st.selectbox("Item Type", ["School Dress", "Shoes", "Textbooks"])
            qr_dist = qrcode_scanner(key='dist_scan')
            if qr_dist:
                std_dist = students_df[students_df['Student Code'].astype(str) == str(qr_dist)]
                if not std_dist.empty:
                    st.success(f"Confirmed: {item} given to {std_dist.iloc[0]['Name']}")
                    # Log distribution logic can be added here

        with tabs[2]:
            st.header("App Maintenance")
            if st.button("🔄 Reload All Data from GitHub"):
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("Enter password to access Head Teacher tools.")