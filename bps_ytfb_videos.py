import streamlit as st
import gspread
from datetime import datetime
import pytz
import time

# ==========================================
# 1. PAGE SETUP & AUTHENTICATION
# ==========================================
st.set_page_config(page_title="BPS Video Tracker", page_icon="🎥", layout="centered")

# --- BACK BUTTON ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("dashboard.py")
st.write("---") 

@st.cache_resource
def init_connection():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        client = gspread.service_account_from_dict(creds_dict)
        return client
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        st.stop()

client = init_connection()

try:
    sheet_project = client.open("BPS YTfb Videos").worksheet("Logs")
    sheet_storage = client.open("BPS YTfb Videos").worksheet("Storage_Logs")
    sheet_files = client.open("BPS YTfb Videos").worksheet("File_Metadata")
    sheet_master = client.open("MY ROUTINE 2026").worksheet("activity_log")
except Exception as e:
    st.error(f"Could not open Google Sheets. Error: {e}")
    st.stop()

# ==========================================
# 2. ARCHITECTURE FUNCTIONS
# ==========================================
def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=60)
def get_master_data():
    return sheet_master.get_all_records()

# ==========================================
# 3. UI DASHBOARD & LOGIC
# ==========================================
st.title("🎥 BPS Video Workflow Tracker")

tab1, tab2, tab3, tab4 = st.tabs(["▶️ Start a Phase", "⏹ Stop & Log", "💾 Storage Tracker", "📁 File Metadata"])

# ------------------------------------------
# TAB 1: START A PHASE (Dynamic Device & Software)
# ------------------------------------------
with tab1:
    st.subheader("Initialize New Video Phase")
    
    # Selection outside form for immediate UI reactivity
    video_phase = st.selectbox(
        "Current Phase", 
        ["Transferring", "Editing", "Rendering", "Publishing (YT)", "Publishing (FB)"]
    )
    
    with st.form("start_task_form"):
        event_name = st.text_input("Event Name (e.g., Annual Sports Day)")
        
        # --- CONDITIONAL FIELDS ---
        if video_phase == "Publishing (YT)":
            yt_title = st.text_input("YouTube Video Title")
            yt_publish_time = st.time_input("Scheduled/Actual Publish Time", value=get_ist_time().time())
            
            recording_device = "N/A"
            editing_tool = "N/A"
            project_metadata = f"{event_name}|{video_phase}|{yt_title}|{yt_publish_time}"
        
        else:
            col1, col2 = st.columns(2)
            with col1:
                # Dynamic device list based on phase
                if video_phase == "Editing":
                    device_options = ["Mi 11x", "PC W10"]
                else:
                    device_options = ["Mi 11x", "DJI Pocket"]
                
                recording_device = st.selectbox("Primary Device", device_options)
            
            with col2:
                # Added Shotcut to the list
                editing_tool = st.selectbox(
                    "Editing Software", 
                    ["Shotcut", "CapCut", "Filmora", "VLLO", "None"]
                )
            
            project_metadata = f"{event_name}|{video_phase}|{recording_device}|{editing_tool}"

        start_button = st.form_submit_button("Start Phase")

        if start_button:
            if not event_name:
                st.error("Please enter an Event Name.")
            elif video_phase == "Publishing (YT)" and not yt_title:
                st.error("Please enter a Video Title.")
            else:
                now = get_ist_time()
                log_date = now.strftime("%Y-%m-%d")
                start_time_str = now.strftime("%H:%M:%S")
                
                gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
                
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
                
                with st.spinner("Logging to Master..."):
                    smart_append_row(sheet_master, row_data)
                    st.success(f"Started {video_phase} successfully!")
                    time.sleep(1)
                    st.rerun()
# ------------------------------------------
# TAB 2: STOP & LOG (Handles YT Metadata)
# ------------------------------------------
with tab2:
    st.subheader("Active Tasks")
    master_records = sheet_master.get_all_values()
    active_tasks = []
    
    for i in range(1, len(master_records)):
        row_data = master_records[i]
        if len(row_data) >= 8 and row_data[2] == "RUNNING" and row_data[4] == "Video Production":
            active_tasks.append({
                "row_index": i + 1,
                "start_time": row_data[1],
                "task_label": row_data[5],
                "metadata": row_data[7]
            })
            
    if active_tasks:
        for task in active_tasks:
            with st.container(border=True):
                st.info(f"**Running:** {task['task_label']} (Started: {task['start_time']})")
                
                if st.button(f"⏹ Stop & Dual-Log", key=f"stop_{task['row_index']}", type="primary"):
                    now = get_ist_time()
                    end_time_log = now.strftime("%H:%M:%S") 
                    
                    try:
                        # 1. Update Master
                        gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
                        sheet_master.update_cell(task['row_index'], 3, end_time_log)
                        sheet_master.update_cell(task['row_index'], 4, gs_formula_master)

                        # 2. Append to Project Sheet
                        meta_parts = task['metadata'].split("|")
                        event = meta_parts[0]
                        phase = meta_parts[1]
                        
                        # Handle specific columns if it was a YouTube Publishing task
                        if phase == "Publishing (YT)":
                            yt_title = meta_parts[2]
                            yt_pub_time = meta_parts[3]
                            # Device and Tool are recorded as the Title and Pub Time for YT phases
                            device_or_title = yt_title 
                            tool_or_pub = yt_pub_time
                        else:
                            device_or_title = meta_parts[2]
                            tool_or_pub = meta_parts[3]

                        gs_formula_project = f'=IF(INDIRECT("G"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("G"&ROW())-INDIRECT("F"&ROW()), 1), "h:mm:ss"), ""))'
                        
                        project_row = [
                            now.strftime("%Y-%m-%d"), event, phase, 
                            device_or_title, tool_or_pub, 
                            task['start_time'], end_time_log, gs_formula_project
                        ]
                        
                        smart_append_row(sheet_project, project_row)
                        st.success("Logged successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.write("No active production tasks.")

# ------------------------------------------
# TAB 3 & 4 (STORAGE & FILES)
# ------------------------------------------
with tab3:
    st.subheader("💾 Storage Tracker")
    with st.form("storage_log_form"):
        event_name_storage = st.text_input("Event Name", key="storage_event")
        device_dumped = st.selectbox("Device Dumped", ["Mobile (Mi 11x)", "DJI Pocket", "PC / External Drive"])
        col1, col2 = st.columns(2)
        with col1: storage_before = st.number_input("Before (GB)", step=0.1)
        with col2: storage_after = st.number_input("After (GB)", step=0.1)
        if st.form_submit_button("Log Storage"):
            if event_name_storage:
                smart_append_row(sheet_storage, [get_ist_time().strftime("%Y-%m-%d"), event_name_storage, device_dumped, storage_before, storage_after, '=D&ROW()-E&ROW()'])
                st.success("Logged!")

with tab4:
    st.subheader("📁 File Metadata")
    with st.form("file_metadata_form", clear_on_submit=True):
        event_f = st.text_input("Event Name")
        f_type = st.radio("Type", ["Raw Footage", "Rendered Video"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            f_name = st.text_input("File Name")
            f_dur = st.text_input("Duration (HH:MM:SS)")
        with col2:
            f_loc = st.selectbox("Location", ["PC Local", "External HDD", "Google Drive", "Mobile"])
            f_time = st.time_input("Record/Render Time")
        if st.form_submit_button("Save File"):
            if f_name and event_f:
                smart_append_row(sheet_files, [get_ist_time().strftime("%Y-%m-%d"), event_f, f_type, f_name, f_loc, f_time.strftime("%H:%M:%S"), f_dur])
                st.success("Saved!")
