import streamlit as st
import gspread
from datetime import datetime
import pytz
import time

# ==========================================
# 1. PAGE SETUP & AUTHENTICATION
# ==========================================
st.set_page_config(page_title="BPS Video Tracker", page_icon="🎥", layout="centered")

# --- BACK BUTTON (STRICTLY REQUIRED HERE) ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("dashboard.py")
st.write("---") 
# --------------------------------------------

@st.cache_resource
def init_connection():
    """Initializes the connection using Streamlit Secrets."""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        client = gspread.service_account_from_dict(creds_dict)
        return client
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        st.stop()

client = init_connection()

# Connect to the specific tabs in both databases
try:
    # Project Tracker Sheets
    sheet_project = client.open("BPS YTfb Videos").worksheet("Logs")
    sheet_storage = client.open("BPS YTfb Videos").worksheet("Storage_Logs")
    sheet_files = client.open("BPS YTfb Videos").worksheet("File_Metadata")
    
    # Master Routine Sheet
    sheet_master = client.open("MY ROUTINE 2026").worksheet("activity_log")
except Exception as e:
    st.error(f"Could not open Google Sheets. Check names and permissions. Error: {e}")
    st.stop()


# ==========================================
# 2. ARCHITECTURE FUNCTIONS
# ==========================================
def get_ist_time():
    """Returns current time strictly in Asia/Kolkata timezone."""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def smart_append_row(sheet, row_data):
    """Safely appends a row to the true bottom of the sheet."""
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try:
        sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
    except TypeError:
        # Fallback for older gspread syntax if needed
        sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=60)
def get_master_data():
    """Fetches the Master Routine data."""
    return sheet_master.get_all_records()

@st.cache_data(ttl=60)
def get_project_data():
    """Fetches the Project specific data."""
    return sheet_project.get_all_records()


# ==========================================
# 3. UI DASHBOARD & LOGIC
# ==========================================
st.title("🎥 BPS Video Workflow Tracker")
st.markdown("Manage your video production phases, assets, and storage.")

# Create FOUR tabs for a comprehensive interface
tab1, tab2, tab3, tab4 = st.tabs(["▶️ Start a Phase", "⏹ Stop & Log", "💾 Storage Tracker", "📁 File Metadata"])

# ------------------------------------------
# TAB 1: START A PHASE (Writes "RUNNING" to Master)
# ------------------------------------------
with tab1:
    with st.form("start_task_form"):
        st.subheader("Initialize New Video Phase")
        
        event_name = st.text_input("Event Name (e.g., Annual Sports Day)")
        
        col1, col2 = st.columns(2)
        with col1:
            video_phase = st.selectbox("Current Phase", ["Transferring", "Editing", "Rendering", "Publishing (YT)", "Publishing (FB)"])
            recording_device = st.selectbox("Primary Device", ["Mi 11x", "DJI Pocket"])
        with col2:
            editing_tool = st.selectbox("Editing Software", ["CapCut", "Filmora", "VLLO", "None"])
            related_devices = st.selectbox("Related Devices", ["None", "DJI Mic Mini", "DJI Osmo Mobile 7p"])

        start_button = st.form_submit_button("Start Phase")

        if start_button:
            if not event_name:
                st.error("Please enter an Event Name.")
            else:
                now = get_ist_time()
                log_date = now.strftime("%Y-%m-%d")
                start_time_str = now.strftime("%H:%M:%S")
                
                # Master Sheet Columns: Date(A), Start(B), End(C), Duration(D), Activity(E), Sub(F), Check(G), Notes(H)
                gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
                
                # Save project details into the "Notes" column temporarily
                project_metadata = f"{event_name}|{video_phase}|{recording_device}|{editing_tool}"

                row_data = [
                    log_date,               # A: Date
                    start_time_str,         # B: Start_Time
                    "RUNNING",              # C: End_Time
                    gs_formula_master,      # D: Duration
                    "Video Production",     # E: Activity
                    f"{video_phase} - {event_name}", # F: Sub_Activities
                    "",                     # G: check_list
                    project_metadata        # H: Notes
                ]
                
                with st.spinner("Starting phase in Master Routine..."):
                    smart_append_row(sheet_master, row_data)
                    get_master_data.clear() 
                    st.success(f"Started '{video_phase}' for '{event_name}' at {start_time_str}!")


# ------------------------------------------
# TAB 2: STOP & LOG (Multiple Task Architecture)
# ------------------------------------------
with tab2:
    st.subheader("Active Tasks")
    
    # Fetch data to find "RUNNING" tasks
    master_records = sheet_master.get_all_values()
    
    # List to hold all active tasks
    active_tasks = []
    
    # Iterate through all rows to find EVERY running task
    for i in range(1, len(master_records)): # Start at 1 to skip headers
        row_data = master_records[i]
        # Check if End_Time (Index 2) is RUNNING and Activity (Index 4) is Video Production
        if len(row_data) >= 8 and row_data[2] == "RUNNING" and row_data[4] == "Video Production":
            active_tasks.append({
                "row_index": i + 1, # Google Sheets is 1-indexed
                "start_time": row_data[1],
                "task_label": row_data[5],
                "metadata": row_data[7]
            })
            
    if active_tasks:
        st.write(f"Found {len(active_tasks)} active task(s):")
        
        # Create a visual block and a Stop button for EACH active task
        for task in active_tasks:
            # Use a container to visually separate multiple tasks
            with st.container(border=True):
                st.info(f"**Currently Running:** {task['task_label']} (Started at {task['start_time']})")
                
                # The 'key' parameter is MANDATORY here so Streamlit can tell the buttons apart
                if st.button(f"⏹ Stop & Dual-Log Task", key=f"stop_btn_{task['row_index']}", type="primary"):
                    now = get_ist_time()
                    end_time_log = now.strftime("%H:%M:%S") 
                    
                    with st.spinner(f"Writing {task['task_label']} to databases..."):
                        try:
                            # --- 1. UPDATE MASTER TRACKER ---
                            gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
                            
                            sheet_master.update_cell(task['row_index'], 3, end_time_log)
                            sheet_master.update_cell(task['row_index'], 4, gs_formula_master)

                            # --- 2. APPEND TO PROJECT TRACKER ---
                            try:
                                event, phase, device, tool = task['metadata'].split("|")
                            except ValueError:
                                event, phase, device, tool = "Unknown", "Unknown", "Unknown", "Unknown"

                            gs_formula_project = f'=IF(INDIRECT("G"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("G"&ROW())-INDIRECT("F"&ROW()), 1), "h:mm:ss"), ""))'
                            
                            project_row_data = [
                                now.strftime("%Y-%m-%d"), # A: Log Date
                                event,                    # B: Event Name
                                phase,                    # C: Video Phase
                                device,                   # D: Recording Device
                                tool,                     # E: Editing Tool
                                task['start_time'],       # F: Start Time
                                end_time_log,             # G: End Time
                                gs_formula_project        # H: Duration Formula
                            ]
                            
                            smart_append_row(sheet_project, project_row_data)

                            # --- 3. CLEAR CACHES & RERUN ---
                            get_master_data.clear()
                            get_project_data.clear()
                            
                            st.success(f"Task '{task['task_label']}' successfully logged!")
                            time.sleep(1.5)
                            st.rerun() # Refresh the page so the stopped task disappears

                        except Exception as e:
                            st.error(f"An error occurred during logging: {e}")
    else:
        st.write("No active video production tasks found. Go to 'Start a Phase' to begin.")

# ------------------------------------------
# TAB 3: STORAGE TRACKER (Logs to Storage_Logs tab)
# ------------------------------------------
with tab3:
    st.subheader("💾 Log Data Dumps & Storage")
    
    with st.form("storage_log_form"):
        event_name_storage = st.text_input("Event Name (e.g., Annual Sports Day)", key="storage_event")
        device_dumped = st.selectbox("Device Dumped", ["Mobile (Mi 11x)", "DJI Pocket", "PC / External Drive"])
        
        col1, col2 = st.columns(2)
        with col1:
            storage_before = st.number_input("Storage BEFORE (GB)", min_value=0.0, step=0.1)
        with col2:
            storage_after = st.number_input("Storage AFTER (GB)", min_value=0.0, step=0.1)
            
        submit_storage = st.form_submit_button("Log Storage Data")
        
        if submit_storage:
            if not event_name_storage:
                st.error("Please enter an Event Name.")
            else:
                now = get_ist_time()
                log_date = now.strftime("%Y-%m-%d")
                
                # Calculated Dump Size (Formula)
                gs_formula_data_dumped = f'=IFERROR(INDIRECT("D"&ROW()) - INDIRECT("E"&ROW()), 0)'
                
                storage_row = [
                    log_date,               # A: Date
                    event_name_storage,     # B: Event
                    device_dumped,          # C: Device
                    storage_before,         # D: Before (GB)
                    storage_after,          # E: After (GB)
                    gs_formula_data_dumped  # F: Calculated Dump Size
                ]
                
                smart_append_row(sheet_storage, storage_row)
                st.success(f"Storage data logged for {device_dumped}!")


# ------------------------------------------
# TAB 4: FILE METADATA (Logs to File_Metadata tab)
# ------------------------------------------
with tab4:
    st.subheader("📁 Log Video Assets")
    
    with st.form("file_metadata_form", clear_on_submit=True): 
        event_name_file = st.text_input("Event Name", key="file_event")
        file_type = st.radio("Asset Type", ["Raw Footage", "Rendered Final Video"], horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            file_name = st.text_input("File Name (e.g., DJI_001.mp4)")
            duration = st.text_input("Video Duration (e.g., 00:15:30)")
        with col2:
            storage_loc = st.selectbox("Storage Location", ["PC Local Drive", "External HDD 1", "Google Drive", "Mobile Gallery"])
            file_time = st.time_input("Time Recorded/Rendered")
            
        submit_file = st.form_submit_button("Save File Metadata")
        
        if submit_file:
            if not file_name or not event_name_file:
                st.error("Event Name and File Name are required.")
            else:
                now = get_ist_time()
                log_date = now.strftime("%Y-%m-%d")
                time_str = file_time.strftime("%H:%M:%S")
                
                file_row = [
                    log_date,           # A: Date
                    event_name_file,    # B: Event
                    file_type,          # C: Raw/Rendered
                    file_name,          # D: File Name
                    storage_loc,        # E: Location
                    time_str,           # F: Time
                    duration            # G: Duration
                ]
                
                smart_append_row(sheet_files, file_row)
                st.success(f"File '{file_name}' saved to asset database!")
