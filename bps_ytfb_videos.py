import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import pytz
import time

# ==========================================
# 1. PAGE SETUP & MEMORY STATE
# ==========================================
st.set_page_config(page_title="BPS Video Tracker", page_icon="🎥", layout="wide")

# --- BACK BUTTON ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("dashboard.py")
st.write("---") 

# --- MEMORY MODULE ---
for key, default_val in [
    ('saved_event', '➕ Create New Event...'),
    ('saved_phase', 'Transferring'),
    ('saved_device', 'Mi 11x'),
    ('saved_software', 'Shotcut'),
    ('saved_dump', 'Mobile (Mi 11x)'),
    ('saved_loc', 'PC Local Drive')
]:
    if key not in st.session_state:
        st.session_state[key] = default_val

def get_idx(opt_list, val):
    return opt_list.index(val) if val in opt_list else 0

# ==========================================
# 2. AUTHENTICATION & AGGRESSIVE CACHING
# ==========================================
@st.cache_resource
def init_connection():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        client = gspread.service_account_from_dict(creds_dict)
        return client
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        st.stop()

@st.cache_resource
def get_worksheets():
    client = init_connection()
    try:
        return {
            "project": client.open("BPS YTfb Videos").worksheet("Logs"),
            "storage": client.open("BPS YTfb Videos").worksheet("Storage_Logs"),
            "files": client.open("BPS YTfb Videos").worksheet("File_Metadata"),
            "master": client.open("MY ROUTINE 2026").worksheet("activity_log")
        }
    except Exception as e:
        st.error(f"Could not open Google Sheets. Error: {e}")
        st.stop()

sheets = get_worksheets()
sheet_project = sheets["project"]
sheet_storage = sheets["storage"]
sheet_files = sheets["files"]
sheet_master = sheets["master"]

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=60)
def get_master_values():
    return sheet_master.get_all_values()

@st.cache_data(ttl=60)
def get_project_history():
    return sheet_project.get_all_records()

@st.cache_data(ttl=60)
def get_event_list():
    history = get_project_history()
    if history:
        df = pd.DataFrame(history)
        if "Event Name" in df.columns:
            events = [str(e).strip() for e in df["Event Name"].unique() if str(e).strip()]
            return sorted(list(set(events)))
    return []

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
    
    unique_events = get_event_list()
    event_options = ["➕ Create New Event..."] + unique_events
    phase_options = ["Transferring", "Editing", "Rendering", "Publishing (YT)", "Publishing (FB)"]
    
    col_evt, col_phase = st.columns(2)
    with col_evt:
        event_selection = st.selectbox("Select Event", event_options, index=get_idx(event_options, st.session_state.saved_event))
    with col_phase:
        video_phase = st.selectbox("Current Phase", phase_options, index=get_idx(phase_options, st.session_state.saved_phase))
    
    with st.form("start_task_form"):
        if event_selection == "➕ Create New Event...":
            event_name = st.text_input("Enter New Event Name (e.g., Annual Sports Day)")
        else:
            event_name = event_selection
            st.info(f"Selected Event: **{event_name}**")
        
        yt_title, yt_publish_time, recording_device, editing_tool = "-", "-", "-", "-"
        
        if video_phase == "Publishing (YT)":
            yt_title = st.text_input("YouTube Video Title")
            col1, col2 = st.columns(2)
            with col1:
                device_opts = ["PC W10", "Mi 11x"]
                recording_device = st.selectbox("Device", device_opts, index=get_idx(device_opts, st.session_state.saved_device))
            with col2:
                yt_publish_time = st.time_input("Scheduled/Actual Publish Time", value=get_ist_time().time())
            editing_tool = "-"
        else:
            col1, col2 = st.columns(2)
            with col1:
                if video_phase == "Editing":
                    device_opts = ["Mi 11x", "PC W10"]
                else:
                    device_opts = ["Mi 11x", "DJI Pocket"]
                recording_device = st.selectbox("Device", device_opts, index=get_idx(device_opts, st.session_state.saved_device))
            with col2:
                soft_opts = ["Shotcut", "CapCut", "Filmora", "VLLO", "None"]
                editing_tool = st.selectbox("Editing Software", soft_opts, index=get_idx(soft_opts, st.session_state.saved_software))
        
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
                    
                    st.session_state.saved_event = event_name
                    st.session_state.saved_phase = video_phase
                    st.session_state.saved_device = recording_device
                    st.session_state.saved_software = editing_tool
                    
                    get_master_values.clear()
                    st.success(f"Started {video_phase} successfully!")
                    time.sleep(1)
                    st.rerun()

# ------------------------------------------
# TAB 2: STOP & LOG
# ------------------------------------------
with tab2:
    st.subheader("Active Tasks")
    master_records = get_master_values()
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

                        meta_parts = task['metadata'].split("|")
                        if len(meta_parts) == 6:
                            event, phase, device, tool, y_title, y_time = meta_parts
                        else:
                            event, phase = meta_parts[0], meta_parts[1]
                            device, tool, y_title, y_time = "-", "-", "-", "-"
                            
                        gs_formula_project = f'=IF(INDIRECT("G"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("G"&ROW())-INDIRECT("F"&ROW()), 1), "h:mm:ss"), ""))'
                        
                        project_row = [
                            now.strftime("%Y-%m-%d"), event, phase, device, tool, 
                            task['start_time'], end_time_log, gs_formula_project, 
                            y_title, y_time
                        ]
                        
                        smart_append_row(sheet_project, project_row)
                        
                        get_master_values.clear()
                        get_project_history.clear()
                        get_event_list.clear() 
                        
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
    
    unique_events = get_event_list()
    event_options_storage = ["➕ Create New Event..."] + unique_events
    event_selection_storage = st.selectbox("Select Event", event_options_storage, index=get_idx(event_options_storage, st.session_state.saved_event), key="tab3_evt")
        
    with st.form("storage_log_form"):
        if event_selection_storage == "➕ Create New Event...":
            event_name_storage = st.text_input("Enter New Event Name")
        else:
            event_name_storage = event_selection_storage
            st.info(f"Selected Event: **{event_name_storage}**")

        dump_opts = ["Mobile (Mi 11x)", "DJI Pocket", "PC / External Drive"]
        device_dumped = st.selectbox("Device Dumped", dump_opts, index=get_idx(dump_opts, st.session_state.saved_dump))
        
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
                
                st.session_state.saved_event = event_name_storage
                st.session_state.saved_dump = device_dumped
                
                st.success(f"Storage data logged for {device_dumped}!")

# ------------------------------------------
# TAB 4: FILE METADATA
# ------------------------------------------
with tab4:
    st.subheader("📁 Log Video Assets")
    
    unique_events = get_event_list()
    event_options_file = ["➕ Create New Event..."] + unique_events
    event_selection_file = st.selectbox("Select Event", event_options_file, index=get_idx(event_options_file, st.session_state.saved_event), key="tab4_evt")
        
    with st.form("file_metadata_form", clear_on_submit=True): 
        if event_selection_file == "➕ Create New Event...":
            event_name_file = st.text_input("Enter New Event Name")
        else:
            event_name_file = event_selection_file
            st.info(f"Selected Event: **{event_name_file}**")

        file_type = st.radio("Asset Type", ["Raw Footage", "Rendered Final Video"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            file_name = st.text_input("File Name (e.g., DJI_001.mp4)")
            duration = st.text_input("Video Duration (e.g., 00:15:30)")
        with col2:
            loc_opts = ["PC Local Drive", "External HDD 1", "Google Drive", "Mobile Gallery"]
            storage_loc = st.selectbox("Storage Location", loc_opts, index=get_idx(loc_opts, st.session_state.saved_loc))
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
                
                st.session_state.saved_event = event_name_file
                st.session_state.saved_loc = storage_loc
                
                st.success(f"File '{file_name}' saved to asset database!")

# ------------------------------------------
# TAB 5: HISTORY & ANALYTICS
# ------------------------------------------
with tab5:
    st.subheader("📊 Analytics & History")
    
    col_filter, col_refresh = st.columns([3, 1])
    with col_filter:
        unique_events = get_event_list()
        filter_options = ["All Events"] + unique_events
        selected_filter = st.selectbox("Filter by Event", filter_options, key="history_filter")
    with col_refresh:
        st.write("") 
        st.write("") 
        if st.button("🔄 Refresh Data", use_container_width=True):
            get_master_values.clear()
            get_project_history.clear()
            get_event_list.clear() 
            st.rerun()

    history_data = get_project_history()
    
    if history_data:
        df = pd.DataFrame(history_data)
        # Clean hidden spaces from column headers
        df.columns = df.columns.str.strip()
        
        # Safe check: Only filter if 'Event Name' exists
        if selected_filter != "All Events" and "Event Name" in df.columns:
            df = df[df["Event Name"] == selected_filter]
            
        if df.empty:
            st.info(f"No completed tasks found for '{selected_filter}'.")
        else:
            # --- PHASE-WISE TIME SUMMARY (ORDERED) ---
            st.markdown("#### ⏱️ Phase-Wise Time Summary")
            
            temp_df = df.copy()
            
            if "Duration" in temp_df.columns and "Video Phase" in temp_df.columns:
                temp_df['Duration'] = temp_df['Duration'].replace(['', None, '-'], '00:00:00')
                temp_df['Duration_td'] = pd.to_timedelta(temp_df['Duration'], errors='coerce').fillna(pd.Timedelta(seconds=0))
                
                # Calculate Grand Total across all phases for this event
                grand_total_td = temp_df['Duration_td'].sum()
                
                # Group by phase and sum the time
                phase_summary = temp_df.groupby("Video Phase")["Duration_td"].sum().reset_index()

                # Define the chronological order for the phases
                phase_order = ["Transferring", "Editing", "Rendering", "Publishing (YT)", "Publishing (FB)"]
                
                # Assign a sort value based on the custom list (unrecognized phases go to the end)
                phase_summary['Sort_Key'] = phase_summary['Video Phase'].apply(
                    lambda x: phase_order.index(x) if x in phase_order else 99
                )
                
                # Sort the dataframe by the chronological key
                phase_summary = phase_summary.sort_values("Sort_Key")

                def format_timedelta(td):
                    total_seconds = int(td.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

                if not phase_summary.empty:
                    # Create enough columns for all present phases + 1 for the Grand Total
                    metric_cols = st.columns(len(phase_summary) + 1)
                    
                    # Output the ordered phase times
                    for i, row in enumerate(phase_summary.itertuples()):
                        formatted_time = format_timedelta(row.Duration_td)
                        # row._1 is the "Video Phase" column
                        metric_cols[i].metric(label=row._1, value=formatted_time)
                        
                    # Output the Grand Total in the final rightmost column
                    metric_cols[-1].metric(label="🌟 GRAND TOTAL", value=format_timedelta(grand_total_td))
            else:
                st.warning("⚠️ Could not calculate time summary. Please ensure column H in your 'Logs' Google Sheet is named exactly 'Duration'.")
            
            st.divider() 
            
            # --- RECENT COMPLETED TASKS LOG ---
            st.markdown("#### 📋 Task Breakdown")
            df_reversed = df.iloc[::-1] 
            
            st.dataframe(
                df_reversed, 
                use_container_width=True, 
                column_config={
                    "Log Date": st.column_config.DateColumn("📅 Date"),
                    "Event Name": "📋 Event", 
                    "Video Phase": "Phase",
                    "Device": "📷 Device", 
                    "Editing Tool": "💻 Software",
                    "YT Title": "📺 YT Title",
                    "YT Publish Time": "⏰ YT Publish Time",
                    "Duration": st.column_config.TextColumn("⏱ Duration")
                }
            )
    else:
        st.info("No completed tasks found in the history log.")
