import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

st.set_page_config(page_title="Future Task Tester", page_icon="🧪")

# --- 1. Google Sheets Connection Setup ---
@st.cache_resource
def init_connection():
    # Make sure you have your credentials in .streamlit/secrets.toml
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

# --- 2. Main UI & Form ---
st.title("🧪 Test Push to 'future_tasks'")
st.write("This safely pushes a 12-column row to your MY ROUTINE 2026 Google Sheet.")

ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)

with st.form("test_future_form", clear_on_submit=True):
    st.subheader("Task Details")
    f_name = st.text_input("Task Name", placeholder="e.g., Fix Attendance Bug")
    f_act = st.selectbox("Activity Category", ["WORK", "HEALTH", "SCH WORK", "HOME", "PEOPLE"])
    f_type = st.radio("Task Type", ["Sub-Activity", "Checklist"], horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1: f_date = st.date_input("Due Date", value=now.date())
    
    # Generate time options
    time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
    with col2: f_time = st.selectbox("Due Time", options=time_opts, index=time_opts.index(now.strftime('%H:%M')))

    st.divider()
    
    # --- Dual-Mode Time Management Inputs ---
    st.subheader("Time Management Strategy")
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        f_role = st.selectbox("Role Context", ["Head Teacher (BPS)", "Developer (BPS Digital)", "YouTube Creator", "Personal", "Transition"])
    with col_f2: 
        f_urg = st.checkbox("🔥 Urgent")
    with col_f3: 
        f_imp = st.checkbox("⭐ Important")
    
    f_energy = st.slider("Expected Energy Requirement", 1, 10, 5, help="1 = Low Energy/Routine, 10 = High Energy/Deep Work")
    
    # --- 3. Submit Logic ---
    submit = st.form_submit_button("🚀 Push to Google Sheets", type="primary", use_container_width=True)
    
    if submit:
        if f_name:
            try:
                # Connect to Sheet
                client = init_connection()
                sheet = client.open("MY ROUTINE 2026").worksheet("future_tasks")
                
                # Construct the 12-item array matching your new backend
                row_data = [
                    f_date.strftime('%Y-%m-%d'),  # 1. Due_Date
                    f_time,                       # 2. Due_Time
                    f_act,                        # 3. Activity
                    f_type,                       # 4. Type
                    f_name.strip(),               # 5. Task_Name
                    "Personal",                   # 6. Entity
                    "Pending",                    # 7. Status
                    "",                           # 8. Cancel_Reason
                    f_role,                       # 9. Role
                    str(f_urg).upper(),           # 10. Urgent
                    str(f_imp).upper(),           # 11. Important
                    f_energy                      # 12. Energy_Level
                ]
                
                # Push to sheet
                sheet.append_row(row_data, value_input_option="USER_ENTERED")
                
                st.success(f"✅ Successfully pushed '{f_name}' to future_tasks!")
                st.write("**Data sent:**", row_data)
                
            except Exception as e:
                st.error(f"❌ Connection Error: Make sure your st.secrets are configured correctly. Details: {e}")
        else:
            st.error("⚠️ Please enter a Task Name before submitting.")
