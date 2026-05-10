import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import pytz
import time

# ==========================================
# 1. PAGE SETUP & AUTHENTICATION
# ==========================================
st.set_page_This is a great update. Tracking which device you are using to publish (like checking if uploading from your PC W10 is faster than your Mi 11x) will give you great insights into your internet/upload bottlenecks.

I have updated the code to include the **Primary Device** dropdown when you select "Publishing (YT)" (defaulting to PC W10 and Mi 11x). I also updated the data table in **Tab 5** to look for your new `"Device"` column header instead of `"Recording Device"`.

Here is the fully updated code. Replace your `bps_ytfb_videos.py` with this block:

```python
import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import pytz
import time

# ==========================================
# 1. PAGE SETUP & AUTHENTICATION
# ==========================================
st.set_page_config(page_title="BPS Video Tracker", page_icon="🎥", layout="wide")

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

@st.cache_data(ttl=60)
def get_project_history():
    return sheet_project.get_all_records()

# ==========================================
# 3. UI DASHBOARD & LOGIC
# ==========================================
st.title("🎥 BPS Video Workflow Tracker")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "▶️ Start a Phase", "⏹ Stop & Log", "💾 Storage Tracker", "📁 File Metadata", "📊 History"
])

# ------------------------------------------
# TAB 1: START A PHASE
# ------------------------------------------
with tab1:
    st.subheader("Initialize New Video Phase")
    
    video_phase = st.selectbox(
        "Current Phase", 
        ["Transferring", "Editing", "Rendering", "Publishing (YT)", "Publishing (FB)"]
    )
    
    with st.form("start_task_form"):
        event_name = st.text_input("Event Name (e.g., Annual Sports Day)")
        
        # Initialize variables
        yt_title, yt_publish_time, recording_device, editing_tool = "-", "-", "-", "-"
        
        if video_phase == "Publishing (YT)":
            yt_title = st.text_input("YouTube Video Title")
            
            col1, col2 = st.columns(2)
            with col1:
                # ADDED: Device selection for Publishing
                recording_device = st.selectbox("Primary Device", ["PC W10", "Mi 11x"])
            with col2:
                yt_publish_time = st.time_input("Scheduled/Actual Publish Time", value=get_ist_time().time())
                
        else:
            col1, col2 = st.columns(2)
            with col1:
                if video_phase == "Editing":
                    device_options = ["Mi 11x", "PC W10"]
                else:
                    device_options = ["Mi 11x", "DJI Pocket"]
                
                recording_device = st.selectbox("Primary Device", device_options)
            with col2:
                editing_tool = st.selectbox("Editing Software", ["Shotcut", "CapCut", "Filmora", "VLLO", "None"])
        
        # 6-PART PAYLOAD
        project_metadata = f"{event_name}|{video_phase}|{recording_device}|{editing_tool}|{yt_title}|{yt_publish_time}"

        if st.form_submit_button("Start Phase"):
            if not event_name:
                st.error("Please enter an Event Name.")
            elif video_phase == "Publishing (YT)" and yt_title == "-":
                st.error("Please enter a VideoThis is an easy update! Now that you have properly separated the YouTube data into its own columns (I and J), we can easily bring the **Primary Device** selector back into the "Publishing (YT)" phase without breaking anything. 

Since you updated Column D's header from "Recording Device" to "Device" in your Google Sheet, I have also updated the labels in the app and the History table (`pandas` mapping) to match your new database structure perfectly.

### Full Updated Code (`bps_ytfb_videos.py`)

Copy and paste this complete script. It includes the new Device layout for YouTube publishing and the updated column references!

```python
import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import pytz
import time

# ==========================================
# 1. PAGE SETUP & AUTHENTICATION
# ==========================================
st.set_page_config(page_title="BPS Video Tracker", page_icon="🎥", layout="wide")

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

@st.cache_data(ttl=60)
def get_project_history():
    return sheet_project.get_all_records()

# ==========================================
# 3. UI DASHBOARD & LOGIC
# ==========================================
st.title("🎥 BPS Video Workflow Tracker")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "▶️ Start a Phase", "⏹ Stop & Log", "💾 Storage Tracker", "📁 File Metadata", "📊 History"
])

# ------------------------------------------
# TAB 1: START A PHASE (Device added to YT)
# ------------------------------------------
with tab1:
    st.subheader("Initialize New Video Phase")
    
    video_phase = st.selectbox(
        "Current Phase", 
        ["Transferring", "Editing", "Rendering", "Publishing (YT)", "Publishing (FB)"]
    )
    
    with st.form("start_task_form"):
        event_name = st.text_input("Event Name (e.g., Annual Sports Day)")
        
        # Initialize variables so they always exist
        yt_title, yt_publish_time, recording_device, editing_tool = "-", "-", "-", "-"
        
        if video_phase == "Publishing (YT)":
            yt_title = st.text_input("YouTube Video Title")
            
            # Show Device and Time together for YT Publishing
            col1, col2 = st.columns(2)
            with col1:
                recording_device = st.selectbox("Device", ["PC W10", "Mi 11x"])
            with col2:
                yt_publish_time = st.time_input("Scheduled/Actual Publish Time", value=get_ist_time().time())
                
            editing_tool = "-" # Not needed for publishing
            
        else:
            col1, col2 = st.columns(2)
            with col1:
                if video_phase == "Editing":
                    device_options = ["Mi 11x", "PC W10"]
                else:
                    device_options = ["Mi 11x", "DJI Pocket"]
                
                recording_device = st.selectbox("Device", device_options)
            with col2:
                editing_tool = st.selectbox("Editing Software", ["Shotcut", "CapCut", "Filmora", "VLLO", "None"])
        
        # NEW 6-PART PAYLOAD: Event | Phase | Device | Tool | YT_Title | YT_Time
        project_metadata = f"{event_name}|{video_phase}|{recording_device}|{editing_tool}|{yt_title}|{yt_publish_time}"

        if st.form_submit_button("Start Phase"):
            if not event_name:
                st.error("Please enter an Event Name.")
            elif video_phase == "Publishing (YT)" and yt_title == "-":
                st.error("Please enter a Video Title.")
            else:
                now = get_ist_time()
                log_date = now.strftime("%Y-%m-%d")
                start_time_str = now.strftime("%H:%M:%S")
                
                gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
                
                row_data = [
                    log_date, start_time_str, "RUNNING", gs_formula_master, 
                    "Video Production", f"{video_phase} - {event_name}", "", project_metadata
                ]
                
                with st.spinner("Logging to Master..."):
                    smart_append_row(sheet_master, row_data)
                    st.success(f"Started {video_phase} successfully!")
                    time.sleep(1)
                    st.rerun()

# ------------------------------------------
# TAB 2: STOP & LOG
# ------------------------------------------
with tab2:
    st.subheader("Active Tasks")
    master_records = sheet_master.get_all_values()
    active_tasks = []
    
    for i in range(1, len(master_records)):
        row_data = master_records[i]
        if len(row_data) >= 8 and row_data[2] == "RUNNING" and row_data[4] == "Video Production":
            active_tasks.append({
                "row_index": i + 1, "start_time": row_data[1], 
                "task_label": row_data[5], "metadata": row_data[7]
            })
            
    if active_tasks:
        for task in active_tasks:
            with st.container(border=True):
                st.info(f"**Running:** {task['task_label']} (Started: {task['start_time']})")
                
                if st.button(f"⏹ Stop & Dual-Log", key=f"stop_{task['row_index']}", type="primary"):
                    now = get_ist_time()
                    end_time_log = now.strftime("%H:%M:%S") 
                    
                    try:
                        gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
                        sheet_master.update_cell(task['row_index'], 3, end_time_log)
                        sheet_master.update_cell(task['row_index'], 4, gs_formula_master)

                        # Parse the metadata
                        meta_parts = task['metadata'].split("|")
                        
                        # Fallback logic to safely handle old tasks
                        if len(meta_parts) == 6:
                            event, phase, device, tool, y_title, y_time = meta_parts
                        else:
                            event, phase = meta_parts[0], meta_parts[1]
                            device, tool, y_title, y_time = "-", "-", "-", "-"
                            
                        gs_formula_project = f'=IF(INDIRECT("G"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("G"&ROW())-INDIRECT("F"&ROW()), 1), "h:mm:ss"), ""))'
                        
                        project_row = [
                            now.strftime("%Y-%m-%d"), # A: Date
                            event,                    # B: Event Name
                            phase,                    # C: Phase
                            device,                   # D: Device
                            tool,                     # E: Tool
                            task['start_time'],       # F: Start
                            end_time_log,             # G: End
                            gs_formula_project,       # H: Duration
                            y_title,                  # I: YT Title
                            y_time                    # J: YT Publish Time
                        ]
                        
                        smart_append_row(sheet_project, project_row)
                        get_project_history.clear()
                        st.success("Logged successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.write("No active production tasks.")

# ------------------------------------------
# TAB 3: STORAGE TRACKER
# ------------------------------------------
with tab3:
    st.subheader("💾 Log Data Dumps & Storage")
    with st.form("storage_log_form"):
        event_name_storage = st.text_input("Event Name (e.g., Annual Sports Day)", key="storage_event")
        device_dumped = st.selectbox("Device Dumped", ["Mobile (Mi 11x)", "DJI Pocket", "PC / External Drive"])
        col1, col2 = st.columns(2)
        with col1: storage_before = st.number_input("Storage BEFORE (GB)", min_value=0.0, step=0.1)
        with col2: storage_after = st.number_input("Storage AFTER (GB)", min_value=0.0, step=0.1)
            
        if st.form_submit_button("Log Storage Data"):
            if not event_name_storage:
                st.error("Please enter an Event Name.")
            else:
                now = get_ist_time()
                gs_formula_data_dumped = f'=IFERROR(INDIRECT("D"&ROW()) - INDIRECT("E"&ROW()), 0)'
                storage_row = [
                    now.strftime("%Y-%m-%d"), event_name_storage, device_dumped, 
                    storage_before, storage_after, gs_formula_data_dumped
                ]
                smart_append_row(sheet_storage, storage_row)
                st.success(f"Storage data logged for {device_dumped}!")

# ------------------------------------------
# TAB 4: FILE METADATA
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
            
        if st.form_submit_button("Save File Metadata"):
            if not file_name or not event_name_file:
                st.error("Event Name and File Name are required.")
            else:
                now = get_ist_time()
                file_row = [
                    now.strftime("%Y-%m-%d"), event_name_file, file_type, file_name, 
                    storage_loc, file_time.strftime("%H:%M:%S"), duration
                ]
                smart_append_row(sheet_files, file_row)
                st.success(f"File '{file_name}' saved to asset database!")

# ------------------------------------------
# TAB 5: HISTORY
# ------------------------------------------
with tab5:
    st.subheader("📊 Recent Completed Tasks")
    if st.button("🔄 Refresh History"):
        get_project_history.clear()
        st.rerun()

    history_data = get_project_history()
    
    if history_data:
        df = pd.DataFrame(history_data)
        
        # Clean column headers
        df.columns = df.columns.str.strip()
        
        # Reverse to show newest first
        df_reversed = df.iloc[::-1] 
        
        st.dataframe(
            df_reversed, 
            use_container_width=True, 
            column_config={
                "Log Date": st.column_config.DateColumn("📅 Date"),
                "Video Phase": "Phase",
                "Device": "📷 Device", # Updated to match your new Google Sheet header
                "Recording Device": "📷 Device", # Failsafe
                "Editing Tool": "💻 Software",
                "YT Title": "📺 YT Title",
                "YT Publish Time": "⏰ YT Publish Time",
                "Duration": st.column_config.TextColumn("⏱ Duration")
            }
        )
    else:
        st.info("No completed tasks found in the history log.")
