import streamlit as st
import pandas as pd
from datetime import datetime
import os
from streamlit_qr_code_scanner import qr_code_scanner

# --- 1. INITIAL SETUP ---
st.set_page_config(page_title="Bhagyabantapur PS Manager", layout="wide")
date_today = datetime.now().strftime("%Y-%m-%d")
day_name = datetime.now().strftime('%A')

# Helper to load CSVs with Bengali Font support (utf-8-sig)
@st.cache_data
def load_school_data(file):
    if os.path.exists(file):
        return pd.read_csv(file, encoding='utf-8-sig')
    return None

students_df = load_school_data('students.csv')
routine_df = load_school_data('routine.csv')

if students_df is None or routine_df is None:
    st.error("⚠️ Files missing! Please ensure students.csv and routine.csv are in the folder.")
    st.stop()

# --- 2. CONFIGURATION ---
SECRET_PASSWORD = "bpsAPP@2026"
TEACHER_MAP = {
    "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS",
    "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP",
    "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("🏫 BPS Digital")
role = st.sidebar.radio("Role:", ["Assistant Teacher (MDM)", "Head Teacher (Admin)"])

# --- ROLE: ASSISTANT TEACHER (SMART MODE) ---
if role == "Assistant Teacher (MDM)":
    st.header("🍱 Teacher Daily Dashboard")
    selected_teacher = st.selectbox("Select Your Name", list(TEACHER_MAP.keys()))
    my_init = TEACHER_MAP[selected_teacher]

    # Smart Filter: Finds the current class from routine.csv
    active_period = routine_df[(routine_df['Day'] == day_name) & (routine_df['Teacher'] == my_init)]
    
    if not active_period.empty:
        row = active_period.iloc[0]
        st.success(f"📍 Scheduled Now: {row['Class']} | {row['Subject']}")
        sel_class, sel_section = row['Class'], row['Section']
    else:
        st.warning(f"No class scheduled for {selected_teacher} on {day_name}.")
        c1, c2 = st.columns(2)
        sel_class = c1.selectbox("Manual Class", students_df['Class'].unique())
        sel_section = c2.selectbox("Manual Section", ["A", "B"])

    # --- HYBRID ENTRY (QR SCAN + CHECKLIST) ---
    st.subheader("📸 Scan ID or 📋 Use Checklist")
    
    # Scanner (Matches 'Student Code' column)
    scanned_id = qr_code_scanner(key='mdm_scan')
    if scanned_id:
        std = students_df[students_df['Student Code'].astype(str) == str(scanned_id)]
        if not std.empty:
            st.info(f"✅ Scanned: {std.iloc[0]['Name']} (Roll: {std.iloc[0]['Roll']})")
        else:
            st.error("ID not recognized.")

    st.divider()
    class_list = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_section)].copy()
    
    if not class_list.empty:
        class_list['Ate_MDM'] = False
        edited_mdm = st.data_editor(
            class_list[['Roll', 'Name', 'Ate_MDM']],
            column_config={"Ate_MDM": st.column_config.CheckboxColumn("MDM Taken?", default=False)},
            disabled=["Roll", "Name"], hide_index=True, use_container_width=True,
            key=f"editor_{sel_class}_{sel_section}"
        )
        
        if st.button("Submit MDM Report"):
            total = edited_mdm['Ate_MDM'].sum()
            summary = pd.DataFrame([{"Date": date_today, "Class": sel_class, "Section": sel_section, "Count": total, "Teacher": my_init}])
            summary.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
            st.success(f"Report Submitted! Total: {total}")
            st.balloons()

# --- ROLE: HEAD TEACHER (ADMIN) ---
elif role == "Head Teacher (Admin)":
    pw = st.sidebar.text_input("Admin Password", type="password")
    if pw == SECRET_PASSWORD:
        st.sidebar.success("Access Granted!")
        tabs = st.tabs(["📊 Reports", "📦 Distribution", "🔄 System Refresh"])
        
        with tabs[1]:
            st.header("Distribution (Dresses/Shoes/Books)")
            dist_item = st.selectbox("Resource", ["School Dress", "Shoes", "Textbooks"])
            qr_dist = qr_code_scanner(key='dist_scan')
            if qr_dist:
                std = students_df[students_df['Student Code'].astype(str) == str(qr_dist)]
                if not std.empty:
                    st.success(f"Log: {dist_item} given to {std.iloc[0]['Name']}")

        with tabs[2]:
            if st.button("🔄 Reload Data from GitHub"):
                st.cache_data.clear()
                st.rerun()