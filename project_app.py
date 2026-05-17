import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import calendar 

# --- Master Google Sheets Formula for Duration ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

# ==========================================
# 1. Configuration & Session State Init
# ==========================================
st.set_page_config(page_title="Project Tracker", page_icon="📊", layout="wide")

if 'pomodoro_state' not in st.session_state:
    st.session_state.pomodoro_state = {}

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 0px !important;
        border: 1px solid #cccccc !important;
        background-color: #ffffff !important;
        box-shadow: none !important;
    }
    
    /* CSS for the pulsing dot animation */
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.9; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.9; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Database Connection
# ==========================================
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

def get_sheet(tab_name):
    client = init_connection()
    return client.open("MY ROUTINE 2026").worksheet(tab_name)

@st.cache_data(ttl=300)
def get_project_tasks():
    client = init_connection()
    ss = client.open("MY ROUTINE 2026")
    try:
        sheet = ss.worksheet("project_tasks")
    except gspread.exceptions.WorksheetNotFound:
        # UPDATED: Now creates 8 columns
        sheet = ss.add_worksheet(title="project_tasks", rows="200", cols="8")
        sheet.append_row(["Task Name", "Project Name", "Activity", "Status", "Start Date", "End Date", "Completed Date", "Creation Date"])
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Task Name", "Project Name", "Activity", "Status", "Start Date", "End Date", "Completed Date", "Creation Date", "row_index"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = "" # UPDATED to 8 columns
    df = df.iloc[:, :8]
    df.columns = ["Task Name", "Project Name", "Activity", "Status", "Start Date", "End Date", "Completed Date", "Creation Date"]
    df['row_index'] = df.index + 2 
    return df

@st.cache_data(ttl=300)
def get_sk_sync_tasks():
    client = init_connection()
    ss = client.open("MY ROUTINE 2026")
    try:
        sheet = ss.worksheet("sk_sync_project")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="sk_sync_project", rows="100", cols="6")
        sheet.append_row(["Project Name", "Phase", "Task / Milestone", "Status", "Est. Time", "Actual Time (Mins)"])
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Project Name", "Phase", "Task / Milestone", "Status", "Est. Time", "Actual Time (Mins)", "row_index"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 6: df[df.shape[1]] = ""
    df = df.iloc[:, :6]
    df.columns = ["Project Name", "Phase", "Task / Milestone", "Status", "Est. Time", "Actual Time (Mins)"]
    df['row_index'] = df.index + 2 
    return df

@st.cache_data(ttl=300)
def get_activity_log():
    sheet = get_sheet("activity_log")
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

# ==========================================
# 3. Dedicated SK-Sync Component
# ==========================================
def render_sk_sync_tracker(sk_sync_tasks, today_str, now, gs_formula):
    st.markdown("### 🔄 Project SK-Sync Progress")
    
    col_m, col_y = st.columns(2)
    with col_m:
        selected_month = st.selectbox("Target Data Month", list(calendar.month_name)[1:], key="sksync_target_month")
    with col_y:
        selected_year = st.selectbox("Target Data Year", [2021, 2022, 2023, 2024, 2025, 2026], index=0, key="sksync_target_year")
    st.markdown("---")
    
    total_tasks = len(sk_sync_tasks)
    if total_tasks == 0:
        st.info("No SK-Sync tasks found. Paste your data into the 'sk_sync_project' tab.")
        return
        
    completed_tasks = len(sk_sync_tasks[sk_sync_tasks['Status'].str.strip().str.title() == 'Done'])
    progress_pct = int((completed_tasks / total_tasks) * 100)
    
    st.progress(progress_pct / 100.0, text=f"Completion: {progress_pct}% ({completed_tasks}/{total_tasks} Tasks Migrated)")
    
    pending = sk_sync_tasks[sk_sync_tasks['Status'].str.strip().str.title() == 'Pending']
    
    if not pending.empty:
        next_task = pending.iloc[0]
        task_name = next_task['Task / Milestone']
        est_time = next_task['Est. Time']
        phase_name = next_task['Phase']
        sheet_row = int(next_task['row_index'])
        
        st.info(f"**🎯 Next Action [{phase_name}]:** {task_name} (~{est_time}) for {selected_month} {selected_year}")
        
        with st.container(border=True):
            st.markdown("**⏱️ Session Time Tracker**")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button("▶️ Start Live Timer", use_container_width=True, type="primary", key="sksync_start_btn"):
                    log_sheet = get_sheet("activity_log")
                    detailed_task_log = f"{task_name} (SK-Sync: {selected_month} {selected_year})"
                    log_sheet.append_row([
                        today_str, now.strftime('%H:%M'), "RUNNING", gs_formula,    
                        "WORK", detailed_task_log, "", "SK-Sync Tracking"
                    ], value_input_option="USER_ENTERED")
                    get_activity_log.clear() 
                    st.rerun()
            
            with col2:
                if st.button("✅ Mark Done (Quick Complete)", use_container_width=True, key="sksync_done_btn"):
                    try:
                        sheet_worksheet = get_sheet("sk_sync_project")
                        headers = sheet_worksheet.row_values(1)
                        status_col = headers.index('Status') + 1
                        sheet_worksheet.update_cell(sheet_row, status_col, 'Done')
                        get_sk_sync_tasks.clear()
                        st.success(f"Awesome! '{task_name}' marked as Done.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to update task: {e}")
    else:
        st.success("🎉 Project SK-Sync is 100% Complete! Your ecosystem is fully synced.")
        if 'Actual Time (Mins)' in sk_sync_tasks.columns:
            total_minutes = pd.to_numeric(sk_sync_tasks['Actual Time (Mins)'], errors='coerce').fillna(0).sum()
            hours, mins = divmod(int(total_minutes), 60)
            st.write(f"**Total Time Invested:** {hours} hours and {mins} minutes.")

# ==========================================
# 4. Main Application Logic
# ==========================================
try:
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    today_str = now.strftime('%Y-%m-%d')

    proj_df = get_project_tasks()
    log_df = get_activity_log()
    sksync_df = get_sk_sync_tasks()
    
    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Notes'].str.strip().isin(['Project Tracking', 'SK-Sync Tracking']))]
    active_count = len(running_tasks)

    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("📊 Project Tracking Dashboard")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Sync Data", use_container_width=True):
            get_project_tasks.clear()
            get_activity_log.clear()
            get_sk_sync_tasks.clear()
            st.toast("Synced with Google Sheets!")
            time.sleep(0.5)
            st.rerun()

    if active_count > 0:
        st.markdown(f"""
            <div style='position: fixed; bottom: 30px; left: 20px; background-color: #ff4b4b; color: white; padding: 8px 16px; border-radius: 20px; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); font-weight: bold; font-size: 16px; z-index: 9999; pointer-events: none; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 16px; margin-right: 6px; animation: pulse 1.5s infinite;'>⏱️</span> {active_count} Project Running
            </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # SECTION A: LIVE TIME TRACKING
    # ==========================================
    pending_projs = pd.DataFrame()
    if not proj_df.empty:
        pending_projs = proj_df[proj_df['Status'].str.strip().str.title() != 'Completed']

    with st.container():
        st.markdown("### ⏱️ Live Time Tracking")
        st.markdown("---")
        
        if active_count > 0:
            st.markdown("<div style='margin-bottom: 10px; color: #d84315;'><b>🟢 Currently Running:</b></div>", unsafe_allow_html=True)
            for idx, active_row in running_tasks.iterrows():
                sheet_row = idx + 2 
                active_sub = str(active_row['Sub_Activities'])
                display_name = active_sub
                
                try:
                    start_dt_str = f"{active_row['Date']} {active_row['Start_Time']}"
                    dt_naive = datetime.strptime(start_dt_str, "%Y-%m-%d %H:%M")
                    active_start_time = ist_timezone.localize(dt_naive)
                    elapsed_time = now - active_start_time
                    mins_elapsed = int(elapsed_time.total_seconds() // 60)
                except: mins_elapsed = 0 
                
                cycle_minute = mins_elapsed % 30
                pomodoro_count = (mins_elapsed // 30) + 1
                current_state = "Focus" if cycle_minute < 25 else "Break"
                task_id = f"task_{sheet_row}"
                
                if task_id in st.session_state.pomodoro_state:
                    if st.session_state.pomodoro_state[task_id] != current_state:
                        components.html("""
                            <script>
                                try {
                                    var ctx = new (window.AudioContext || window.webkitAudioContext)();
                                    function playBeep(freq, time, dur) {
                                        var osc = ctx.createOscillator();
                                        var gain = ctx.createGain();
                                        osc.connect(gain);
                                        gain.connect(ctx.destination);
                                        osc.frequency.value = freq;
                                        osc.type = "square";
                                        gain.gain.setValueAtTime(0.1, time);
                                        gain.gain.exponentialRampToValueAtTime(0.001, time + dur);
                                        osc.start(time);
                                        osc.stop(time + dur);
                                    }
                                    playBeep(600, ctx.currentTime, 0.2);
                                    playBeep(800, ctx.currentTime + 0.2, 0.3);
                                } catch(e) {}
                            </script>
                        """, height=0, width=0)
                        
                st.session_state.pomodoro_state[task_id] = current_state

                if current_state == "Focus":
                    p_state = "🍅 Focus Time"
                    p_color = "#d84315"
                    p_left = 25 - cycle_minute
                    p_prog = cycle_minute / 25.0
                else:
                    p_state = "☕ Break Time"
                    p_color = "#2e7b32"
                    p_left = 30 - cycle_minute
                    p_prog = (cycle_minute - 25) / 5.0
                
                st.markdown(f"""
                <div style='background-color: #f8f9fa; border-left: 5px solid {p_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <strong style='font-size: 16px; color: #333;'>⏳ {display_name}</strong>
                        <span style='color: #666; font-size: 14px;'>Total: {mins_elapsed}m</span>
                    </div>
                    <div style='margin-top: 8px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;'>
                        <span style='color: {p_color}; font-weight: bold; font-size: 14px;'>{p_state} (Cycle {pomodoro_count})</span>
                        <span style='color: #555; font-size: 13px; font-weight: bold;'>{p_left}m left</span>
                    </div>
                    <div style='width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 6px;'>
                        <div style='width: {p_prog * 100}%; background-color: {p_color}; height: 6px; border-radius: 4px; transition: width 0.5s ease;'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                is_sksync = (str(active_row['Notes']).strip() == 'SK-Sync Tracking')
                raw_task_name = active_sub.split(" (")[0].strip()
                
                col_stat, col_stop, col_cancel = st.columns([2, 1, 1])
                
                with col_stat:
                    if is_sksync:
                        sk_matches = sksync_df[sksync_df['Task / Milestone'].str.strip() == raw_task_name]
                        curr_stat = sk_matches.values[0][3].strip().title() if not sk_matches.empty else "Pending"
                        status_opts = ["Pending", "Done"]
                        try: def_idx = status_opts.index(curr_stat)
                        except ValueError: def_idx = 0
                        new_proj_status = st.selectbox("Update SK-Sync Status:", status_opts, index=def_idx, key=f"pstat_{sheet_row}", label_visibility="collapsed")
                    else:
                        curr_stat_matches = proj_df[proj_df['Task Name'] == raw_task_name]['Status']
                        curr_stat = curr_stat_matches.values[0].strip().title() if not curr_stat_matches.empty else "In Progress"
                        status_opts = ["In Progress", "Completed", "Not Started"]
                        try: def_idx = status_opts.index(curr_stat)
                        except ValueError: def_idx = 0
                        new_proj_status = st.selectbox("Update Status upon saving:", status_opts, index=def_idx, key=f"pstat_{sheet_row}", label_visibility="collapsed")
                
                with col_stop:
                    if st.button("🛑 SAVE", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                        end_time_log = now.time()
                        log_sheet = get_sheet("activity_log")
                        log_sheet.update_cell(sheet_row, 3, end_time_log.strftime('%H:%M')) 
                        log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                                
                        if is_sksync and new_proj_status:
                            sk_matches = sksync_df[sksync_df['Task / Milestone'].str.strip() == raw_task_name]
                            if not sk_matches.empty:
                                sk_idx = int(sk_matches.iloc[0]['row_index'])
                                sk_sheet = get_sheet("sk_sync_project")
                                
                                sk_sheet.update_cell(sk_idx, 4, new_proj_status)
                                
                                existing_mins = pd.to_numeric(sk_matches.iloc[0]['Actual Time (Mins)'], errors='coerce')
                                if pd.isna(existing_mins): existing_mins = 0
                                total_mins = int(existing_mins) + mins_elapsed
                                
                                sk_sheet.update_cell(sk_idx, 6, total_mins)
                                get_sk_sync_tasks.clear()
                                
                        elif not is_sksync and new_proj_status:
                            p_matches = proj_df[proj_df['Task Name'] == raw_task_name]
                            if not p_matches.empty:
                                p_idx = int(p_matches.iloc[0]['row_index'])
                                psheet = get_sheet("project_tasks")
                                # Status is Column 4 (D)
                                psheet.update_cell(p_idx, 4, new_proj_status)
                                # If marked as completed here, update Column 7 (G)
                                if new_proj_status == "Completed":
                                    psheet.update_cell(p_idx, 7, today_str)
                                get_project_tasks.clear() 
                                
                        get_activity_log.clear() 
                        st.success(f"Saved: {display_name}")
                        time.sleep(1)
                        st.rerun()

                with col_cancel:
                    if st.button("❌ CANCEL", key=f"cancel_{sheet_row}", use_container_width=True):
                        log_sheet = get_sheet("activity_log")
                        log_sheet.delete_rows(sheet_row)
                        get_activity_log.clear() 
                        st.warning(f"Cancelled: {display_name}")
                        time.sleep(1)
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        if not pending_projs.empty:
            running_subs = running_tasks['Sub_Activities'].tolist()
            avail_projs = pending_projs[~pending_projs['Task Name'].isin([x.split(" (")[0] for x in running_subs])]
            
            if not avail_projs.empty:
                st.markdown("<div style='margin-bottom: 5px; color: #0068c9;'><b>🚀 Start working on a Project Task:</b></div>", unsafe_allow_html=True)
                
                col_proj, col_task, col_btn = st.columns([2, 2, 1])
                
                with col_proj:
                    unique_projs = sorted(avail_projs['Project Name'].unique().tolist())
                    selected_project = st.selectbox("Select Project", unique_projs, label_visibility="collapsed", key="live_proj_sel")
                
                with col_task:
                    filtered_tasks = avail_projs[avail_projs['Project Name'] == selected_project]['Task Name'].tolist()
                    selected_task = st.selectbox("Select Task", filtered_tasks, label_visibility="collapsed", key="live_task_sel")

                with col_btn:
                    st.markdown(
                        """
                        <div id="proj_start_anchor"></div>
                        <style>
                        div[data-testid="column"]:nth-of-type(3) div.element-container:has(#proj_start_anchor) + div.element-container button {
                            background-color: #2e7b32 !important; 
                            color: white !important;
                            border: none !important;
                        }
                        div[data-testid="column"]:nth-of-type(3) div.element-container:has(#proj_start_anchor) + div.element-container button:hover {
                            background-color: #1b5e20 !important; 
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )
                    if st.button("▶️ Start Timer", key="start_proj", use_container_width=True):
                        selected_p_task_full = f"{selected_task} ({selected_project})"
                        
                        task_row = proj_df[(proj_df['Task Name'] == selected_task) & (proj_df['Project Name'] == selected_project)].iloc[0]
                        r_idx = int(task_row['row_index'])
                        curr_stat = task_row['Status'].strip().title()
                        
                        task_activity = str(task_row['Activity']).strip().upper()
                        if not task_activity: 
                            task_activity = "WORK"
                        
                        psheet = get_sheet("project_tasks")
                        
                        if curr_stat == "Not Started":
                            psheet.update_cell(r_idx, 4, "In Progress")
                            get_project_tasks.clear() 
                            
                        log_sheet = get_sheet("activity_log")
                        log_sheet.append_row([
                            today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                            task_activity, selected_p_task_full, "", "Project Tracking"
                        ], value_input_option="USER_ENTERED")
                        get_activity_log.clear() 
                        st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ==========================================
    # SECTION B: SK-SYNC MIGRATION TRACKER
    # ==========================================
    with st.container():
        render_sk_sync_tracker(sksync_df, today_str, now, GS_FORMULA)
    
    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # ==========================================
    # SECTION C: ACTIVE PROJECT TASKS (GROUPED)
    # ==========================================
    st.markdown("### 📋 Active Project Tasks")
    st.markdown("---")
    
    active_df = proj_df[proj_df['Status'].str.strip().str.title() != 'Completed'].copy()

    if active_df.empty:
        st.info("🎉 All caught up! No active tasks pending.")
    else:
        active_df['Project Name'] = active_df['Project Name'].replace("", "Uncategorized Tasks")
        grouped = active_df.groupby('Project Name')
        
        for project, group in grouped:
            st.markdown(f"<h3 style='color: #d84315; margin-top: 15px; border-bottom: 2px solid #f0f2f6; padding-bottom: 5px;'>📂 {project}</h3>", unsafe_allow_html=True)
            
            for _, row in group.iterrows():
                sheet_row = int(row['row_index'])
                
                with st.container():
                    col_chk, col_info = st.columns([0.05, 0.95])
                    
                    with col_chk:
                        st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
                        is_done = st.checkbox(" ", key=f"chk_{sheet_row}_{project}")
                        
                        if is_done:
                            psheet = get_sheet("project_tasks")
                            psheet.update_cell(sheet_row, 4, "Completed") # Update Status to Col D
                            psheet.update_cell(sheet_row, 7, today_str)   # Update Completed Date to Col G
                            get_project_tasks.clear()
                            st.toast(f"✅ Marked '{row['Task Name']}' as Completed!")
                            time.sleep(1)
                            st.rerun()
                            
                    with col_info:
                        c_date = str(row.get('Creation Date', '')).strip()
                        c_str = f" | 🕒 Created: {c_date}" if c_date else ""
                        
                        st.markdown(f"""
                        <div style="background-color: #f8f9fa; padding: 10px 15px; border-radius: 6px; border-left: 5px solid #0068c9; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                            <strong style='font-size: 16px; color: #333;'>{row['Task Name']}</strong><br>
                            <span style='font-size: 13px; color: #666;'>
                                🎯 <b>{row['Activity']}</b> | 🗓️ {row['Start Date']} to {row['End Date']}{c_str}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
        
    st.markdown("---")    
    
    # ==========================================
    # SECTION D: ADD NEW TASK FORM
    # ==========================================
    with st.expander("➕ Add New Project Task", expanded=proj_df.empty):
        with st.form("add_project_task", clear_on_submit=True):
            p_task = st.text_input("Task Name")
            
            # --- FETCH EXISTING DROPDOWNS ---
            if not proj_df.empty:
                existing_projects = ["-- Select Existing Project --"] + sorted(list(set(proj_df['Project Name'].dropna().tolist())))
            else:
                existing_projects = ["-- Select Existing Project --"]
                
            if not log_df.empty:
                existing_activities = ["-- Select Existing Activity --"] + sorted(list(set([a for a in log_df['Activity'].unique().tolist() if a])))
            else:
                existing_activities = ["-- Select Existing Activity --", "WORK", "LEARN", "HEALTH", "CHORES"]
            
            col_p1, col_p2 = st.columns(2)
            with col_p1: p_name_sel = st.selectbox("Existing Project", existing_projects)
            with col_p2: p_name_new = st.text_input("OR New Project Name", placeholder="Type new name here")
            
            # --- NEW: ACTIVITY SELECTORS ---
            col_a1, col_a2 = st.columns(2)
            with col_a1: p_activity_sel = st.selectbox("Existing Activity (From Log)", existing_activities)
            with col_a2: p_activity_new = st.text_input("OR New Activity Tag", placeholder="e.g., WORK, LEARN")
            
            col_s, col_d1, col_d2 = st.columns(3)
            with col_s: p_status = st.selectbox("Status", ["Not Started", "In Progress", "Completed"])
            with col_d1: p_start = st.date_input("Start Date")
            with col_d2: p_end = st.date_input("End Date")
            
            if st.form_submit_button("Add Task", type="primary", use_container_width=True):
                final_p_name = p_name_new.strip() if p_name_new.strip() else (p_name_sel if p_name_sel != "-- Select Existing Project --" else "")
                
                final_p_activity = p_activity_new.strip().upper() if p_activity_new.strip() else (p_activity_sel if p_activity_sel != "-- Select Existing Activity --" else "WORK")
                
                if p_task and final_p_name:
                    psheet = get_sheet("project_tasks")
                    
                    comp_date = today_str if p_status == "Completed" else ""
                    
                    # Columns: 1=Task Name, 2=Project Name, 3=Activity, 4=Status, 5=Start Date, 6=End Date, 7=Completed Date, 8=Creation Date
                    psheet.append_row([
                        p_task.strip(), 
                        final_p_name, 
                        final_p_activity, 
                        p_status, 
                        p_start.strftime('%Y-%m-%d'), 
                        p_end.strftime('%Y-%m-%d'),
                        comp_date,
                        today_str
                    ])
                    get_project_tasks.clear() 
                    st.success(f"Task added successfully under '{final_p_activity}' activity!")
                    time.sleep(1)
                    st.rerun()
                else: 
                    st.error("Task Name and Project Name are both required.")

except Exception as e:
    st.error(f"System Error: {e}")
