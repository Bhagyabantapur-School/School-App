import streamlit as st
import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. Setup Google Sheets API Connection via Streamlit Secrets ---
# Define the required scopes
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Pull the service account information from Streamlit's secret manager
try:
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=scopes
    )
    client = gspread.authorize(credentials)
    
    # Open the exact sheet you shared with the service account
    sheet = client.open("MDM RETURN LOG").sheet1
    
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop() # Stop the app if authentication fails

# --- 2. Streamlit UI and Logic ---
st.title("MDM Return Task Logger")

# Define the pending tasks from your workflow
tasks = [
    "ROUGH02 | RICE OPENING BALANCE UPDATE",
    "MDCF 2 | Rice OPENING BALANCE UPDATE",
    "Report | Reset for this month",
    "MDCF 1 | Fund Opening Balance update",
    "MDCF 1 | Received update",
    "ROUGH02 | Rice receive update",
    "MDCF 2 | Rice receive update",
    "ROUGH01 | All data complite",
    "ROUGH02 | All data complite",
    "MDCF 2 | Rice consumption check",
    "Daily Details | Reset for this month",
    "Daily Details | Update MENU",
    "Front Page | Days, Meal check",
    "Front Page | খ) ভাউচারের বিবরণ adjust"
]

selected_task = st.selectbox("Select MDM Task", tasks)

# Initialize session state to hold the start time
if "start_time" not in st.session_state:
    st.session_state.start_time = None

col1, col2 = st.columns(2)

# Start Button Logic
with col1:
    if st.button("▶ Start Task", use_container_width=True):
        st.session_state.start_time = datetime.datetime.now()
        st.info(f"Task started at: {st.session_state.start_time.strftime('%H:%M')}")

# Stop Button & Data Push Logic
with col2:
    if st.button("⏹ Stop & Log Task", use_container_width=True):
        if st.session_state.start_time:
            # We are using a spinner so you know the API is working
            with st.spinner("Logging to Google Sheets..."):
                stop_time = datetime.datetime.now()
                start_time = st.session_state.start_time
                
                # Format dates and times to match your CSV structure
                date_str = start_time.strftime('%d-%b-%Y')
                start_str = start_time.strftime('%H:%M')
                stop_str = stop_time.strftime('%H:%M')
                
                # Calculate duration
                delta = stop_time - start_time
                total_minutes = int(delta.total_seconds() // 60)
                hours, minutes = divmod(total_minutes, 60)
                duration_str = f"{hours}:{minutes:02d}"
                
                # Split the dropdown selection back into 'Sheet' and 'Work' columns
                sheet_name, work_name = selected_task.split(" | ", 1)
                
                # Prepare the row
                row_data = [sheet_name, work_name, date_str, start_str, stop_str, duration_str]
                
                # Push the row to Google Sheets
                try:
                    sheet.append_row(row_data)
                    st.success(f"Logged successfully! Duration: {duration_str}")
                    st.write("Data appended to sheet:", row_data)
                except Exception as e:
                    st.error(f"Error saving to sheet: {e}")
                
                # Reset the timer for the next task
                st.session_state.start_time = None
        else:
            st.warning("Please start the task first!")
