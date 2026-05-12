import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import time

# ==========================================
# 1. Configuration & Global Variables
# ==========================================
st.set_page_config(page_title="Mi 11X Backup Tracker", layout="centered", page_icon="📱")

ROUTINE_DATA = {
    "Day 1: The Purge (Decluttering)": [
        "Uninstall unused/unnecessary apps",
        "Clear cached data via Settings > About Phone > Storage",
        "Delete outdated APKs and PDFs in the Downloads folder"
    ],
    "Day 2: WhatsApp Backup": [
        "Open WhatsApp Settings > Chats > Chat backup",
        "Toggle 'Include videos' ON",
        "Tap 'Back Up' over Wi-Fi"
    ],
    "Day 3: Cloud Sync for Photos & Docs": [
        "Turn on Google Photos backup and select specific device folders (e.g., Screenshots)",
        "Upload important local documents and scripts to Google Drive"
    ],
    "Day 4: Heavy Media Transfer (SSD/PC)": [
        "Connect phone to PC or an external SSD via USB-C",
        "Copy the DCIM folder (Camera photos/videos)",
        "Copy the Movies/Video folders (Video projects)",
        "Copy the Music/Audio folders (Voiceovers, music)"
    ],
    "Day 5: App Data & System Settings": [
        "Go to Settings > Google > Backup",
        "Ensure 'Backup by Google One' is turned ON",
        "Tap 'Back up now' to save call history, SMS, and Wi-Fi passwords"
    ],
    "Day 6: The Audit": [
        "Manually export backups from standalone apps (e.g., Authenticator apps)",
        "Verify you know your Google and Mi Account passwords"
    ],
    "Day 7: Factory Reset & Rebuild": [
        "Ensure battery is charged to >50%",
        "Go to Settings > About phone > Factory reset > Erase all data",
        "Reboot, log into Google, and restore the backup"
    ]
}

# ==========================================
# 2. Database Connection
# ==========================================
@st.cache_resource
def init_connection():
    """Authenticates using the existing GCP service account credentials."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

@st.cache_resource
def get_backup_spreadsheet():
    """Connects to the newly created Mi_11X_Backup sheet."""
    client = init_connection()
    return client.open("Mi_11X_Backup")

def get_or_create_worksheet():
    """Gets the 'Progress' tab, creating it and adding headers if it doesn't exist."""
    ss = get_backup_spreadsheet()
    try:
        sheet = ss.worksheet("Progress")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="Progress", rows="100", cols="3")
        sheet.append_row(["Day", "Task", "Status"])
    return sheet

@st.cache_data(ttl=60)
def fetch_cloud_progress():
    """Fetches the current progress from Google Sheets."""
    sheet = get_or_create_worksheet()
    data = sheet.get_all_values()
    
    if len(data) <= 1:
        # If the sheet only has headers (or is empty), initialize it with all tasks set to False
        initial_data = []
        for day, tasks in ROUTINE_DATA.items():
            for task in tasks:
                initial_data.append([day, task, "FALSE"])
        
        if initial_data:
            # Append all rows at once for efficiency
            sheet.append_rows(initial_data, value_input_option="USER_ENTERED")
            return pd.DataFrame(initial_data, columns=["Day", "Task", "Status"])
        return pd.DataFrame(columns=["Day", "Task", "Status"])
        
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def update_cloud_task(day, task, is_completed):
    """Updates a specific task's status in Google Sheets."""
    sheet = get_or_create_worksheet()
    # Find the specific cell row that matches the Day and Task
    try:
        # We fetch all values to find the correct row index
        records = sheet.get_all_records()
        row_index = next((index for (index, d) in enumerate(records) if d["Day"] == day and d["Task"] == task), None)
        
        if row_index is not None:
            # Google Sheets is 1-indexed, and we have a header row, so add 2
            sheet_row = row_index + 2 
            status_str = "TRUE" if is_completed else "FALSE"
            sheet.update_cell(sheet_row, 3, status_str) # Column 3 is 'Status'
            return True
    except Exception as e:
        st.error(f"Error syncing to cloud: {e}")
        return False

# ==========================================
# 3. Main Application UI & Logic
# ==========================================
st.title("📱 Mi 11X Factory Reset Tracker")
st.write("A daily 15-minute routine tracker to safely secure all your files, media, and app data before wiping the device.")

# Fetch data from Google Sheets
try:
    df_progress = fetch_cloud_progress()
    
    # Initialize session state from the cloud data if it exists
    if 'completed_tasks' not in st.session_state:
        st.session_state.completed_tasks = []
        if not df_progress.empty:
            # Find all tasks marked as "TRUE" in the cloud and add them to session state
            completed_df = df_progress[df_progress['Status'].astype(str).str.upper() == 'TRUE']
            for _, row in completed_df.iterrows():
                task_id = f"{row['Day']}_{row['Task']}"
                st.session_state.completed_tasks.append(task_id)

    # Progress Calculation
    total_tasks = sum(len(tasks) for tasks in ROUTINE_DATA.values())
    completed_count = len(st.session_state.completed_tasks)
    progress = completed_count / total_tasks if total_tasks > 0 else 0

    st.progress(progress)
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"**Progress:** {completed_count}/{total_tasks} tasks completed")
    with col2:
        if st.button("🔄 Sync", use_container_width=True):
            fetch_cloud_progress.clear()
            st.toast("✅ Synced with Google Sheets!")
            time.sleep(0.5)
            st.rerun()
            
    st.markdown("---")

    # Render Checkboxes
    for day, tasks in ROUTINE_DATA.items():
        st.subheader(day)
        for task in tasks:
            task_id = f"{day}_{task}"
            is_checked = task_id in st.session_state.completed_tasks
            
            # The checkbox UI
            if st.checkbox(task, value=is_checked, key=task_id):
                # If checked in UI but NOT in session state (User just clicked it ON)
                if task_id not in st.session_state.completed_tasks:
                    st.session_state.completed_tasks.append(task_id)
                    with st.spinner("Syncing..."):
                        update_cloud_task(day, task, True)
                        fetch_cloud_progress.clear()
                    st.rerun()
            else:
                # If UNchecked in UI but WAS in session state (User just clicked it OFF)
                if task_id in st.session_state.completed_tasks:
                    st.session_state.completed_tasks.remove(task_id)
                    with st.spinner("Syncing..."):
                        update_cloud_task(day, task, False)
                        fetch_cloud_progress.clear()
                    st.rerun()

    # Celebration Logic
    if progress == 1.0:
        st.success("🎉 All tasks completed! Your data is secure, and the Mi 11X is ready for a clean factory reset.")
        st.balloons()

except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Please ensure 'Mi_11X_Backup' exists and is shared with your service account. Details: {e}")
