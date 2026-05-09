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
    sheet_project = client.open("BPS YTfb Videos").worksheet("Logs")
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
st.markdown("Manage your video production phases and synchronize with your Master Routine.")

# Create two tabs for a cleaner interface
tab1, tab2 = st.tabs(["▶️ Start a Phase", "⏹ Stop & Log"])

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
                
                # We save the project details into the "Notes" column temporarily so we can retrieve them when stopping
                project_metadata = f"{event_name}|{video_phase}|{recording_device}|{editing_tool}"

                row_data = [
                    log_date,               # A: Date
                    start_time_str,         # B: Start_Time
                    "RUNNING",              # C: End_Time
                    gs_formula_master,      # D: Duration
                    "Video Production",     # E: Activity
                    f"{video_phase} - {event_name}", # F: Sub_Activities
                    "",                     # G: check_list
                    project_metadata        # H: Notes (Hidden payload for Tab 2)
                ]
                
                with st.spinner("Starting phase in Master Routine..."):
                    smart_append_row(sheet_master, row_data)
                    get_master_data.clear() # Clear cache
                    st.success(f"Started '{video_phase}' for '{event_name}' at {start_time_str}!")


# ------------------------------------------
# TAB 2: STOP & LOG (Dual Logging Architecture)
# ------------------------------------------
with tab2:
    st.subheader("Active Tasks")
    
    # Fetch data to find "RUNNING" tasks
    master_records = sheet_master.get_all_values()
    
    # Find the row index and data where End_Time (Column C / index 2) is "RUNNING"
    running_task = None
    running_row_index = -1
    
    # Iterate backwards to find the most recent running task
    for i in range(len(master_records)-1, 0, -1):
        if master_records[i][2] == "RUNNING" and master_records[i][4] == "Video Production":
            running_task = master_records[i]
            running_row_index = i + 1 # +1 because Google Sheets is 1-indexed
            break
            
    if running_task:
        # Extract data from the Master Sheet row
        start_time_recorded = running_task[1]
        task_label = running_task[5]
        metadata_raw = running_task[7] # Metadata we hid in the Notes column
        
        st.info(f"**Currently Running:** {task_label} (Started at {start_time_recorded})")
        
        if st.button("⏹ Stop & Dual-Log Task", type="primary"):
            now = get_ist_time()
            end_time_log = now.strftime("%H:%M:%S") 
            
            with st.spinner("Writing to Master and Project databases..."):
                try:
                    # --- 1. UPDATE MASTER TRACKER ---
                    gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
                    
                    # Overwrite End_Time (Col 3) and Duration (Col 4)
                    sheet_master.update_cell(running_row_index, 3, end_time_log)
                    sheet_master.update_cell(running_row_index, 4, gs_formula_master)

                    # --- 2. APPEND TO PROJECT TRACKER ---
                    # Parse the metadata we saved when starting
                    try:
                        event, phase, device, tool = metadata_raw.split("|")
                    except ValueError:
                        # Fallback if metadata is corrupted
                        event, phase, device, tool = "Unknown", "Unknown", "Unknown", "Unknown"

                    # Project Columns: Date(A), Event(B), Phase(C), Device(D), Tool(E), Start(F), End(G), Duration(H)
                    gs_formula_project = f'=IF(INDIRECT("G"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("G"&ROW())-INDIRECT("F"&ROW()), 1), "h:mm:ss"), ""))'
                    
                    project_row_data = [
                        now.strftime("%Y-%m-%d"), # A: Log Date
                        event,                    # B: Event Name
                        phase,                    # C: Video Phase
                        device,                   # D: Recording Device
                        tool,                     # E: Editing Tool
                        start_time_recorded,      # F: Start Time
                        end_time_log,             # G: End Time
                        gs_formula_project        # H: Duration Formula
                    ]
                    
                    smart_append_row(sheet_project, project_row_data)

                    # --- 3. CLEAR CACHES & RERUN ---
                    get_master_data.clear()
                    get_project_data.clear()
                    
                    st.success("Task successfully logged to both databases!")
                    time.sleep(1.5)
                    st.rerun()

                except Exception as e:
                    st.error(f"An error occurred during logging: {e}")
    else:
        st.write("No active video production tasks found. Go to 'Start a Phase' to begin.")
