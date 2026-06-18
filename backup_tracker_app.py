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
from datetime import datetime

# ==========================================
# 1. Configuration & Global Variables
# ==========================================
st.set_page_config(page_title="Mi 11X Backup Suite", layout="centered", page_icon="📱")

ROUTINE_DATA = {
    "Day 1: The Purge (Decluttering)": [
        "Log and uninstall unused apps (Use Tab 2)",
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
# 2. Database Connection & Sheet Setup
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
    """Connects to the Mi_11X_Backup sheet."""
    client = init_connection()
    return client.open("Mi_11X_Backup")

# --- Worksheet Getters & Creators ---
def get_or_create_progress_sheet():
    ss = get_backup_spreadsheet()
    try:
        sheet = ss.worksheet("Progress")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="Progress", rows="100", cols="3")
        sheet.append_row(["Day", "Task", "Status"])
    return sheet

def get_or_create_uninstalled_sheet():
    ss = get_backup_spreadsheet()
    try:
        sheet = ss.worksheet("Uninstalled_Apps")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="Uninstalled_Apps", rows="200", cols="4")
        sheet.append_row(["App Name", "Login ID / Account", "Size (MB)", "Date Logged"])
    return sheet

def get_or_create_storage_sheet():
    ss = get_backup_spreadsheet()
    try:
        sheet = ss.worksheet("Storage_Log")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="Storage_Log", rows="100", cols="10")
        sheet.append_row(["Date", "Apps & Data", "Images", "Audio", "Video", "APKs", "Documents", "System Files", "System", "Total Used (GB)"])
    return sheet

def get_or_create_update_sheet():
    ss = get_backup_spreadsheet()
    try:
        sheet = ss.worksheet("Update")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="Update", rows="100", cols="9")
        sheet.append_row(["Date", "Time", "Details of Update", "AI", "Short", "Lines", "Features", "Selected from AI", "Chat"])
    return sheet

# --- Data Fetchers ---
@st.cache_data(ttl=60)
def fetch_cloud_progress():
    sheet = get_or_create_progress_sheet()
    data = sheet.get_all_values()
    if len(data) <= 1:
        initial_data = [[day, task, "FALSE"] for day, tasks in ROUTINE_DATA.items() for task in tasks]
        if initial_data:
            sheet.append_rows(initial_data, value_input_option="USER_ENTERED")
            return pd.DataFrame(initial_data, columns=["Day", "Task", "Status"])
        return pd.DataFrame(columns=["Day", "Task", "Status"])
    return pd.DataFrame(data[1:], columns=data[0])

@st.cache_data(ttl=60)
def fetch_uninstalled_apps():
    sheet = get_or_create_uninstalled_sheet()
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["App Name", "Login ID / Account", "Size (MB)", "Date Logged"])
    return pd.DataFrame(data[1:], columns=data[0])

@st.cache_data(ttl=60)
def fetch_storage_log():
    sheet = get_or_create_storage_sheet()
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Apps & Data", "Images", "Audio", "Video", "APKs", "Documents", "System Files", "System", "Total Used (GB)"])
    return pd.DataFrame(data[1:], columns=data[0])

@st.cache_data(ttl=60)
def fetch_update_log():
    sheet = get_or_create_update_sheet()
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Time", "Details of Update", "AI", "Short", "Lines", "Features", "Selected from AI", "Chat"])
    return pd.DataFrame(data[1:], columns=data[0])

# --- Data Updaters ---
def update_cloud_task(day, task, is_completed):
    sheet = get_or_create_progress_sheet()
    try:
        records = sheet.get_all_records()
        row_index = next((index for (index, d) in enumerate(records) if d["Day"] == day and d["Task"] == task), None)
        if row_index is not None:
            sheet_row = row_index + 2 
            sheet.update_cell(sheet_row, 3, "TRUE" if is_completed else "FALSE")
            return True
    except Exception as e:
        st.error(f"Error syncing to cloud: {e}")
        return False

def add_uninstalled_app(app_name, login_id, size_mb):
    sheet = get_or_create_uninstalled_sheet()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    sheet.append_row([app_name, login_id, size_mb, date_str])

def add_storage_snapshot(date_label, apps, images, audio, video, apks, docs, sysfiles, system, total):
    sheet = get_or_create_storage_sheet()
    sheet.append_row([date_label, apps, images, audio, video, apks, docs, sysfiles, system, total])

def add_update_log_entry(date_val, time_val, details, ai_used, short_desc, lines_num, features, selected_ai, chat_link):
    sheet = get_or_create_update_sheet()
    sheet.append_row([date_val, time_val, details, ai_used, short_desc, lines_num, features, selected_ai, chat_link])

# ==========================================
# 3. Main Application UI & Logic
# ==========================================
st.title("📱 Mi 11X Reset & Backup Suite")
st.write("Track your daily backup checklist, log app credentials, map your storage progress, and record dev updates.")

try:
    tab1, tab2, tab3, tab4 = st.tabs(["📋 7-Day Checklist", "🗑️ App Uninstallation Log", "📊 Storage Space Tracker", "📝 Update Log"])

    # --- TAB 1: 7-DAY CHECKLIST ---
    with tab1:
        df_progress = fetch_cloud_progress()
        
        if 'completed_tasks' not in st.session_state:
            st.session_state.completed_tasks = []
            if not df_progress.empty:
                completed_df = df_progress[df_progress['Status'].astype(str).str.upper() == 'TRUE']
                for _, row in completed_df.iterrows():
                    task_id = f"{row['Day']}_{row['Task']}"
                    st.session_state.completed_tasks.append(task_id)

        total_tasks = sum(len(tasks) for tasks in ROUTINE_DATA.values())
        completed_count = len(st.session_state.completed_tasks)
        progress = completed_count / total_tasks if total_tasks > 0 else 0

        st.progress(progress)
        
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**Progress:** {completed_count}/{total_tasks} tasks completed")
        with col2:
            if st.button("🔄 Sync", key="sync_btn_1", use_container_width=True):
                fetch_cloud_progress.clear()
                st.toast("✅ Synced with Google Sheets!")
                time.sleep(0.5)
                st.rerun()
                
        st.markdown("---")

        for day, tasks in ROUTINE_DATA.items():
            st.subheader(day)
            for task in tasks:
                task_id = f"{day}_{task}"
                is_checked = task_id in st.session_state.completed_tasks
                
                if st.checkbox(task, value=is_checked, key=task_id):
                    if task_id not in st.session_state.completed_tasks:
                        st.session_state.completed_tasks.append(task_id)
                        with st.spinner("Syncing..."):
                            update_cloud_task(day, task, True)
                            fetch_cloud_progress.clear()
                        st.rerun()
                else:
                    if task_id in st.session_state.completed_tasks:
                        st.session_state.completed_tasks.remove(task_id)
                        with st.spinner("Syncing..."):
                            update_cloud_task(day, task, False)
                            fetch_cloud_progress.clear()
                        st.rerun()

        if progress == 1.0:
            st.success("🎉 All tasks completed! Your data is secure, and the Mi 11X is ready for a clean factory reset.")
            st.balloons()

    # --- TAB 2: APP UNINSTALLATION LOG ---
    with tab2:
        st.subheader("🗑️ Record App Details Before Uninstalling")
        
        with st.form("app_log_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                new_app = st.text_input("App Name *", placeholder="e.g., Kinemaster, SBI Yono")
                app_size = st.number_input("App Size (MB)", min_value=0.0, step=1.0)
            with col_b:
                app_login = st.text_input("Login ID / Email / Phone", placeholder="e.g., user@email.com")
            
            submit_app = st.form_submit_button("Save to Cloud Log")
            
            if submit_app:
                if new_app.strip():
                    with st.spinner("Saving to Google Sheets..."):
                        add_uninstalled_app(new_app.strip(), app_login.strip(), app_size)
                        fetch_uninstalled_apps.clear()
                    st.success(f"Successfully logged {new_app.strip()}!")
                else:
                    st.error("App Name is required.")

        st.markdown("---")
        df_apps = fetch_uninstalled_apps()
        if not df_apps.empty:
            st.dataframe(df_apps, use_container_width=True)
            st.caption(f"Total apps logged: {len(df_apps)}")
        else:
            st.info("No apps logged yet.")

    # --- TAB 3: STORAGE SPACE TRACKER ---
    with tab3:
        st.subheader("📊 Track Storage Metrics Over Time")

        with st.form("storage_entry_form", clear_on_submit=True):
            log_time = st.text_input("Label/Date:", value=datetime.now().strftime("%Y-%m-%d"))
            
            c1, c2 = st.columns(2)
            with c1:
                f_apps = st.number_input("Apps and data (GB)", min_value=0.0, step=0.1, format="%.2f")
                f_images = st.number_input("Images (GB)", min_value=0.0, step=0.1, format="%.2f")
                f_audio = st.number_input("Audio (GB)", min_value=0.0, step=0.1, format="%.2f")
                f_video = st.number_input("Video (GB)", min_value=0.0, step=0.1, format="%.2f")
            with c2:
                f_apks = st.number_input("APKs (GB)", min_value=0.0, step=0.1, format="%.2f")
                f_docs = st.number_input("Documents (GB)", min_value=0.0, step=0.1, format="%.2f")
                f_sysfiles = st.number_input("System files (GB)", min_value=0.0, step=0.1, format="%.2f")
                f_system = st.number_input("System (GB)", min_value=0.0, step=0.1, format="%.2f")
                
            submit_metrics = st.form_submit_button("Save Storage Snapshot to Cloud")
            
            if submit_metrics:
                total_calc = sum([f_apps, f_images, f_audio, f_video, f_apks, f_docs, f_sysfiles, f_system])
                with st.spinner("Saving snapshot..."):
                    add_storage_snapshot(log_time, f_apps, f_images, f_audio, f_video, f_apks, f_docs, f_sysfiles, f_system, round(total_calc, 2))
                    fetch_storage_log.clear()
                st.success("Storage snapshot securely logged!")

        st.markdown("---")
        df_storage = fetch_storage_log()
        
        if not df_storage.empty:
            st.dataframe(df_storage, use_container_width=True)
            df_storage["Total Used (GB)"] = pd.to_numeric(df_storage["Total Used (GB)"], errors='coerce')
            st.line_chart(df_storage.set_index("Date")["Total Used (GB)"])
        else:
            st.info("No storage snapshots saved yet.")

    # --- TAB 4: UPDATE LOG (DEVELOPER CHANGELOG) ---
    with tab4:
        st.subheader("📝 Developer Update Log")
        st.write("Track changes, new features, and the AI tools used to build this application.")

        with st.form("update_log_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                # Auto-fills with current date and time
                u_date = st.text_input("Date", value=datetime.now().strftime("%Y-%m-%d"))
                u_ai = st.text_input("AI Used", placeholder="e.g., Gemini 1.5 Pro, ChatGPT 4")
                u_short = st.text_input("Short Summary", placeholder="e.g., Added Update Tab")
                u_features = st.text_input("Features Added", placeholder="e.g., Gspread Integration, Forms")
            with col2:
                u_time = st.text_input("Time", value=datetime.now().strftime("%H:%M"))
                u_lines = st.number_input("Lines of Code", min_value=0, step=10)
                u_selected = st.text_input("Selected from AI", placeholder="e.g., Yes, Snippet #2")
                u_chat = st.text_input("Chat Reference / Link", placeholder="e.g., Chat: 'Mi 11X Reset'")
            
            u_details = st.text_area("Details of Update", placeholder="Describe what changed in this version...")

            submit_update = st.form_submit_button("Log Update to Cloud")

            if submit_update:
                with st.spinner("Logging update..."):
                    add_update_log_entry(u_date, u_time, u_details, u_ai, u_short, u_lines, u_features, u_selected, u_chat)
                    fetch_update_log.clear()
                st.success("Update log saved successfully!")

        st.markdown("---")
        st.write("### 📜 Cloud Database: Changelog History")
        df_updates = fetch_update_log()
        
        if not df_updates.empty:
            st.dataframe(df_updates, use_container_width=True)
        else:
            st.info("No updates logged yet.")

except Exception as e:
    st.error(f"Failed to connect to Google Sheets or process data. Details: {e}")
