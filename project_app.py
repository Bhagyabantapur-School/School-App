import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px

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
        sheet = ss.add_worksheet(title="project_tasks", rows="200", cols="5")
        sheet.append_row(["Task Name", "Project Name", "Status", "Start Date", "End Date"])
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Task Name", "Project Name", "Status", "Start Date", "End Date", "row_index"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 5: df[df.shape[1]] = ""
    df = df.iloc[:, :5]
    df.columns = ["Task Name", "Project Name", "Status", "Start Date", "End Date"]
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
# 3. Main Application Logic
# ==========================================
try:
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    today_str = now.strftime('%Y-%m-%d')

    proj_df = get_project_tasks()
    log_df = get_activity_log()
    
    # Filter for currently running Project Tasks
    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Notes'].str.strip() == 'Project Tracking')]
    active_count = len(running_tasks)

    # --- HEADER & SYNC ---
    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("📊 Project Tracking Dashboard")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Sync Data", use_container_width=True):
            get_project_tasks.clear()
            get_activity_log.clear()
            st.toast("Synced with Google Sheets!")
            time.sleep(0.5)
            st.rerun()

    # --- FLOATING ACTIVE BADGE ---
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
        
        # 1. RENDER RUNNING PROJECT TASKS
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
                
                # --- POMODORO LOGIC & BEEP TRIGGER ---
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
                    p_color = "#d84315" # Deep Orange
                    p_left = 25 - cycle_minute
                    p_prog = cycle_minute / 25.0
                else:
                    p_state = "☕ Break Time"
                    p_color = "#2e7b32" # Green
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
                
                raw_task_name = active_sub.split(" (")[0]
                curr_stat_matches = proj_df[proj_df['Task Name'] == raw_task_name]['Status']
                curr_stat = curr_stat_matches.values[0].strip().title() if not curr_stat_matches.empty else "In Progress"
                
                status_opts = ["In Progress", "Completed", "Not Started"]
                try:
                    def_idx = status_opts.index(curr_stat)
                except ValueError:
                    def_idx = 0
                    
                col_stat, col_stop, col_cancel = st.columns([2, 1, 1])
                with col_stat:
                    new_proj_status = st.selectbox("Update Status upon saving:", status_opts, index=def_idx, key=f"pstat_{sheet_row}", label_visibility="collapsed")
                
                with col_stop:
                    if st.button("🛑 SAVE", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                        end_time_log = now.time()
                        log_sheet = get_sheet("activity_log")
                        log_sheet.update_cell(sheet_row, 3, end_time_log.strftime('%H:%M')) 
                        log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                                
                        if new_proj_status:
                            p_matches = proj_df[proj_df['Task Name'] == raw_task_name]
                            if not p_matches.empty:
                                p_idx = int(p_matches.iloc[0]['row_index'])
                                psheet = get_sheet("project_tasks")
                                psheet.update_cell(p_idx, 3, new_proj_status)
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

        # 2. START A NEW TASK TIMER
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
                        r_idx = int(proj_df[(proj_df['Task Name'] == selected_task) & (proj_df['Project Name'] == selected_project)]['row_index'].values[0])
                        psheet = get_sheet("project_tasks")
                        curr_stat = proj_df[(proj_df['Task Name'] == selected_task) & (proj_df['Project Name'] == selected_project)]['Status'].values[0].strip().title()
                        
                        if curr_stat == "Not Started":
                            psheet.update_cell(r_idx, 3, "In Progress")
                            get_project_tasks.clear() 
                            
                        log_sheet = get_sheet("activity_log")
                        log_sheet.append_row([
                            today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                            "WORK", selected_p_task_full, "", "Project Tracking"
                        ], value_input_option="USER_ENTERED")
                        get_activity_log.clear() 
                        st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ==========================================
    # SECTION B: DASHBOARD CHARTS & DATA
    # ==========================================
    status_colors = {"Completed": "#2e7b32", "In Progress": "#0068c9", "Not Started": "#ff9f36"}
    
    if not proj_df.empty:
        plot_df = proj_df.copy()
        plot_df['Start Date'] = pd.to_datetime(plot_df['Start Date'], errors='coerce')
        plot_df['End Date'] = pd.to_datetime(plot_df['End Date'], errors='coerce')
        plot_df = plot_df.dropna(subset=['Start Date', 'End Date'])
        
        if not plot_df.empty:
            # --- OVERALL PROGRESS CARDS ---
            st.markdown("### 📈 Overall Progress")
            project_stats = plot_df.groupby('Project Name').apply(
                lambda x: (x['Status'].str.strip().str.title() == 'Completed').sum() / len(x)
            ).reset_index(name='Progress')
            
            cols = st.columns(4) 
            for i, row in project_stats.iterrows():
                with cols[i % 4]:
                    percent_complete = int(row['Progress'] * 100)
                    st.markdown(f"""
                    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 5px; height: 110px;'>
                        <p style='margin: 0; font-size: 16px; font-weight: 600; color: #333; line-height: 1.2; word-wrap: break-word;'>{row['Project Name']}</p>
                        <h2 style='margin: 0; color: #0068c9; padding-top: 5px;'>{percent_complete}%</h2>
                    </div>
                    """, unsafe_allow_html=True)
                    st.progress(row['Progress'])
                    st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- CHARTS SECTION ---
            col_gantt, col_pie = st.columns([2, 1])
            
            with col_gantt:
                st.markdown("#### 🗓️ Task Timeline")
                plot_df['Status'] = plot_df['Status'].str.strip().str.title()
                plot_df = plot_df.sort_values('Start Date')
                
                fig_gantt = px.timeline(plot_df, x_start="Start Date", x_end="End Date", y="Task Name", 
                                        color="Status", color_discrete_map=status_colors, hover_data=["Project Name"])
                fig_gantt.update_yaxes(autorange="reversed", tickmode='linear')
                fig_gantt.update_layout(margin=dict(l=0, r=0, t=30, b=0), xaxis_title="", yaxis_title="", showlegend=False)
                st.plotly_chart(fig_gantt, use_container_width=True)
                
            with col_pie:
                st.markdown("#### 📌 Task Status Breakdown")
                status_counts = plot_df['Status'].value_counts().reset_index()
                status_counts.columns = ['Status', 'Count']
                
                fig_pie = px.pie(status_counts, names='Status', values='Count', 
                                 color='Status', color_discrete_map=status_colors, hole=0.45)
                fig_pie.update_layout(margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Project dates are missing or invalid. Please update them in the Google Sheet.")
    else:
        st.info("No project tasks found. Add your first task below!")
        
    st.markdown("---")    
    
    # ==========================================
    # SECTION C: ADD NEW TASK FORM
    # ==========================================
    with st.expander("➕ Add New Project Task", expanded=proj_df.empty):
        with st.form("add_project_task", clear_on_submit=True):
            p_task = st.text_input("Task Name")
            
            if not proj_df.empty:
                existing_projects = ["-- Select Existing Project --"] + sorted(list(set(proj_df['Project Name'].dropna().tolist())))
            else:
                existing_projects = ["-- Select Existing Project --"]
            
            col_p1, col_p2 = st.columns(2)
            with col_p1: p_name_sel = st.selectbox("Existing Project", existing_projects)
            with col_p2: p_name_new = st.text_input("OR New Project Name", placeholder="Type new name here")
            
            col_s, col_d1, col_d2 = st.columns(3)
            with col_s: p_status = st.selectbox("Status", ["Not Started", "In Progress", "Completed"])
            with col_d1: p_start = st.date_input("Start Date")
            with col_d2: p_end = st.date_input("End Date")
            
            if st.form_submit_button("Add Task", type="primary", use_container_width=True):
                final_p_name = p_name_new.strip() if p_name_new.strip() else (p_name_sel if p_name_sel != "-- Select Existing Project --" else "")
                
                if p_task and final_p_name:
                    psheet = get_sheet("project_tasks")
                    psheet.append_row([p_task.strip(), final_p_name, p_status, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                    get_project_tasks.clear() 
                    st.success("Task added successfully!")
                    time.sleep(1)
                    st.rerun()
                else: 
                    st.error("Task Name and Project Name are both required.")

except Exception as e:
    st.error(f"System Error: {e}")
