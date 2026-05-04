import streamlit as st
import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. Setup Google Sheets API Connection ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=scopes
    )
    client = gspread.authorize(credentials)
    
    # Open the entire spreadsheet first
    spreadsheet = client.open("MDM RETURN LOG")
    
    # Target the first sheet for logging (Index 0 is always the first tab from the left)
    log_sheet = spreadsheet.get_worksheet(0) 
    
    # Target the CONFIG sheet specifically by name for reading the dropdown options
    config_sheet = spreadsheet.worksheet("CONFIG")
    
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop() # Stop the app if authentication fails

# --- 2. Fetch Tasks Dynamically from CONFIG Tab ---
try:
    # get_all_records() automatically reads the first row as headers 
    # and returns a list of dictionaries (e.g., [{'Sheet': 'ROUGH02', 'Work': 'Update'}, ...])
    config_data = config_sheet.get_all_records()
    
    tasks = []
    for row in config_data:
        sheet_val = str(row.get('Sheet', '')).strip()
        work_val = str(row.get('Work', '')).strip()
        
        # Combine them for the dropdown, ensuring empty rows are ignored
        if sheet_val or work_val: 
            tasks.append(f"{sheet_val} | {work_val}")
            
    if not tasks:
        tasks = ["No tasks found in CONFIG sheet"]

except Exception as e:
    st.error(f"Failed to read CONFIG sheet: {e}")
    tasks = ["Error loading tasks"]

# --- 3. Streamlit UI and Logic ---
st.title("MDM Return Task Logger")

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
            # Prevent logging if there's an error with the config sheet
            if selected_task in ["No tasks found in CONFIG sheet", "Error loading tasks"]:
                st.error("Cannot log without valid tasks from CONFIG tab.")
            else:
                with st.spinner("Logging to Google Sheets..."):
                    stop_time = datetime.datetime.now()
                    start_time = st.session_state.start_time
                    
                    # Format dates and times
                    date_str = start_time.strftime('%d-%b-%Y')
                    start_str = start_time.strftime('%H:%M')
                    stop_str = stop_time.strftime('%H:%M')
                    
                    # Calculate duration
                    delta = stop_time - start_time
                    total_minutes = int(delta.total_seconds() // 60)
                    hours, minutes = divmod(total_minutes, 60)
                    duration_str = f"{hours}:{minutes:02d}"
                    
                    # Safely split the dropdown selection back into 'Sheet' and 'Work'
                    parts = selected_task.split(" | ", 1)
                    sheet_name = parts[0] if len(parts) > 0 else ""
                    work_name = parts[1] if len(parts) > 1 else ""
                    
                    # Prepare the row
                    row_data = [sheet_name, work_name, date_str, start_str, stop_str, duration_str]
                    
                    # Push the row specifically to the log_sheet
                    try:
                        log_sheet.append_row(row_data)
                        st.success(f"Logged successfully! Duration: {duration_str}")
                        st.write("Data appended to sheet:", row_data)
                    except Exception as e:
                        st.error(f"Error saving to sheet: {e}")
                    
                    # Reset the timer for the next task
                    st.session_state.start_time = None
        else:
            st.warning("Please start the task first!")
