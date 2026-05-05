import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

# --- Master Google Sheets Formulas for Duration ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'
MDM_GS_FORMULA = '=IF(INDIRECT("E"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("E"&ROW())-INDIRECT("D"&ROW()), 1), "h:mm"), ""))'

# ==========================================
# 1. Configuration & Session State Init
# ==========================================
st.set_page_config(page_title="MDM Return Logger", page_icon="📦", layout="wide")

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
    
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.9; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.9; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Database Connection & Caching Helpers
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

@st.cache_resource
def get_main_spreadsheet():
    client = init_connection()
    return client.open("MY ROUTINE 2026")

@st.cache_resource
def get_mdm_spreadsheet():
    client = init_connection()
    return client.open("MDM RETURN LOG")

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try:
        sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
    except TypeError:
        sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=300)
def get_activity_log():
    ss = get_main_spreadsheet()
    sheet = ss.worksheet("activity_log")
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    return df

@st.cache_data(ttl=300)
def fetch_mdm_config():
    try:
        ss = get_mdm_spreadsheet()
        return ss.worksheet("CONFIG").get_all_records()
    except Exception as e:
        st.error(f"Failed to fetch MDM CONFIG data: {e}")
        return []

# --- Custom Month Generator ---
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)

def get_month_options():
    months = []
    curr_month = now.month
    curr_year = now.year
    for i in range(-3, 6): # 3 months ago to 5 months ahead
        m = curr_month + i
        y = curr_year
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        months.append(datetime(y, m, 1).strftime("%B %Y"))
    return months

# ==========================================
# 3. Google Sheets Write Logic 
# ==========================================
def reset_mdm_config():
    try:
        ss = get_mdm_spreadsheet()
        config_sheet = ss.worksheet("CONFIG")
        all_data = config_sheet.get_all_values()
        num_tasks = len(all_data) - 1 # exclude header
        
        if num_tasks > 0:
            # Create a 1D array updating ONLY Column D (Status)
            update_values = [["Not Started"] for _ in range(num_tasks)]
            # Update ONLY Column D (from D2 down to the end)
            config_sheet.update(range_name=f"D2:D{num_tasks+1}", values=update_values)
        return True
    except Exception as e:
        st.error(f"Failed to reset CONFIG: {e}")
        return False

def update_task_status_in_config(sheet_name, work_name, new_status):
    try:
        ss = get_mdm_spreadsheet()
        config_sheet = ss.worksheet("CONFIG")
        all_data = config_sheet.get_all_values()
        
        for idx, row in enumerate(all_data):
            if idx > 0 and len(row) >= 2: # Skip header
                if str(row[0]).strip() == sheet_name and str(row[1]).strip() == work_name:
                    # Update Column D (Status) for the matched row
                    config_sheet.update(range_name=f"D{idx+1}", values=[[new_status]])
                    break
    except Exception as e:
        st.error(f"Failed to update task status in CONFIG: {e}")

# ==========================================
# 4. Sidebar & UI Layout setup
# ==========================================
today_str = now.strftime('%Y-%m-%d')
mdm_date_str = now.strftime('%d-%b-%Y') 

st.sidebar.title("📅 App Configuration")
month_options = get_month_options()
current_month_str = now.strftime("%B %Y")
default_idx = month_options.index(current_month_str) if current_month_str in month_options else 3

# GLOBAL MONTH SELECTOR
selected_app_month = st.sidebar.selectbox(
    "Select MDM Return Month:", 
    month_options, 
    index=default_idx
)

st.sidebar.markdown("---")
st.sidebar.info("Select the target month before starting or resetting tasks.")

tab_dashboard, tab_settings = st.tabs(["📦 MDM Dashboard", "⚙️ Settings & Reset"])

try:
    log_df = get_activity_log()
    config_raw = fetch_mdm_config()
    
    # Calculate tasks dynamically from CONFIG based on Status
    total_tasks = len([row for row in config_raw if str(row.get('Sheet', '')).strip()])
    completed_count = len([row for row in config_raw if str(row.get('Status', '')).strip().upper() == "COMPLETED"])
    
    available_tasks = [
        f"{row['Sheet']} | {row['Work']}" for row in config_raw 
        if str(row.get('Sheet', '')).strip() and str(row.get('Status', '')).strip().upper() != "COMPLETED"
    ]
    
    if not available_tasks and total_tasks > 0:
        available_tasks = ["🎉 All MDM tasks completed!"]
    elif not available_tasks:
        available_tasks = ["No valid tasks found in CONFIG"]

    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Notes'] == 'MDM Return Task')]
    active_count = len(running_tasks)
    
    progress_val = completed_count / total_tasks if total_tasks > 0 else 0
    progress_percentage = int(progress_val * 100)

    # ==========================================
    # TAB 1: MAIN DASHBOARD
    # ==========================================
    with tab_dashboard:
        col_title, col_sync = st.columns([4, 1])
        with col_title:
            st.markdown(f"<h1 style='margin-top: 0px; margin-bottom: 0px;'>📦 MDM RETURN PREPARE</h1>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='color: gray; margin-top: 0px;'>Target: {selected_app_month}</h4>", unsafe_allow_html=True)
            
        with col_sync:
            st.markdown("<br>", unsafe_allow_html=True) 
            if st.button("🔄 Sync Data", use_container_width=True):
                get_activity_log.clear()
                fetch_mdm_config.clear() 
                st.toast("Synced with Google Sheets!")
                time.sleep(1.0)
                st.rerun()

        # --- ATTRACTIVE PROGRESS BOX ---
        st.markdown(
            """
            <div id="progress_box_anchor"></div>
            <style>
            div.element-container:has(#progress_box_anchor) + div[data-testid="stHorizontalBlock"] {
                background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);
                border: 1px solid #7dd3fc;
                border-radius: 16px;
                padding: 15px 25px;
                box-shadow: 0 4px 12px rgba(14, 165, 233, 0.15);
                align-items: center; 
                margin-bottom: 25px;
                margin-top: 15px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        col_text, col_chart = st.columns([1.5, 1])
        with col_text:
            st.markdown(f"""
                <div style='display: flex; flex-direction: column; justify-content: center;'>
                    <h3 style='margin: 0; color: #1e3a8a; font-size: 26px; font-weight: 700;'>Progress</h3>
                    <p style='margin: 5px 0 0 0; color: #64748b; font-size: 16px; font-weight: 500;'>{completed_count} of {total_tasks} tasks finished</p>
                </div>
            """, unsafe_allow_html=True)

        with col_chart:
            import plotly.graph_objects as go
            remaining = 100 - progress_percentage
            fig = go.Figure(data=[go.Pie(
                values=[progress_percentage, remaining], labels=['Completed', 'Pending'],
                hole=0.75, marker=dict(colors=['#0068c9', '#e2e8f0']), textinfo='none', hoverinfo='label+percent'
            )])
            fig.update_layout(
                annotations=[dict(text=f"<b>{progress_percentage}%</b>", x=0.5, y=0.5, font_size=24, showarrow=False, font=dict(color="#0068c9"))],
                showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=130, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
        st.markdown("---")

        # --- 1. RENDER RUNNING MDM TASKS ---
        if active_count > 0:
            st.markdown("### ⏱️ Active Task")
            for idx, active_row in running_tasks.iterrows():
                sheet_row = idx + 2 
                display_name = str(active_row['Sub_Activities'])
                
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
                    p_state, p_color, p_left, p_prog = "🍅 Focus Time", "#0068c9", 25 - cycle_minute, cycle_minute / 25.0
                else:
                    p_state, p_color, p_left, p_prog = "☕ Rest", "#2e7b32", 30 - cycle_minute, (cycle_minute - 25) / 5.0
                
                st.markdown(f"""
                <div style='background-color: #f8f9fa; border-left: 5px solid {p_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <strong style='font-size: 16px;'>⏳ {display_name}</strong>
                        <span style='color: #666; font-size: 14px;'>Total: {mins_elapsed}m</span>
                    </div>
                    <div style='margin-top: 8px; margin-bottom: 4px; display: flex; justify-content: space-between;'>
                        <span style='color: {p_color}; font-weight: bold; font-size: 14px;'>{p_state} (Cycle {pomodoro_count})</span>
                        <span style='color: #555; font-size: 13px; font-weight: bold;'>{p_left}m left</span>
                    </div>
                    <div style='width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 6px;'>
                        <div style='width: {p_prog * 100}%; background-color: {p_color}; height: 6px; border-radius: 4px;'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                task_status = st.selectbox("Update Task Status:", ["In Progress", "Completed"], index=0, key=f"status_{sheet_row}")
                
                col_stop, col_cancel = st.columns([1, 1])
                with col_stop:
                    if st.button("🛑 STOP & LOG", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                        end_time_log = now.strftime('%H:%M')
                        
                        # Update Master Activity Log
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.update_cell(sheet_row, 3, end_time_log) 
                        log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                        
                        parts = display_name.split(" | ", 1)
                        sheet_name = parts[0] if len(parts) > 0 else ""
                        work_name = parts[1] if len(parts) > 1 else ""
                        start_str = active_row['Start_Time']
                        
                        # Format row for MDM RETURN LOG -> Logs tab
                        # Col A: Sheet, Col B: Work, Col C: Date, Col D: Start, Col E: Stop, Col F: Duration, Col G: Month
                        row_data = [sheet_name, work_name, mdm_date_str, start_str, end_time_log, MDM_GS_FORMULA, selected_app_month]
                        
                        try:
                            # 1. Append to the Logs tab
                            mdm_ss = get_mdm_spreadsheet()
                            mdm_target_sheet = mdm_ss.get_worksheet(0) 
                            smart_append_row(mdm_target_sheet, row_data)
                            
                            # 2. Update Status ONLY in CONFIG tab (Column D)
                            update_task_status_in_config(sheet_name, work_name, task_status)
                            
                            get_activity_log.clear() 
                            fetch_mdm_config.clear() 
                            st.success(f"Saved: Logged to both DBs and status updated!")
                            time.sleep(1.0)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to complete logging process: {e}")

                with col_cancel:
                    if st.button("❌ CANCEL", key=f"cancel_{sheet_row}", use_container_width=True):
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.delete_rows(sheet_row)
                        get_activity_log.clear() 
                        st.warning(f"Cancelled")
                        time.sleep(1.0)
                        st.rerun()

        # --- 2. START NEW TASK UI ---
        if active_count == 0:
            st.markdown("<div style='margin-bottom: 5px; color: #0068c9;'><b>🚀 Start New MDM Task:</b></div>", unsafe_allow_html=True)
            selected_task = st.selectbox("Select Task from Config", available_tasks, key="start_mdm_sel")
            
            if st.button("▶️ Start Task", key="start_mdm_btn", use_container_width=True, type="primary"):
                if "🎉" in selected_task or "No valid" in selected_task:
                    st.error("Cannot start. No valid pending tasks available.")
                else:
                    main_ss = get_main_spreadsheet()
                    log_sheet = main_ss.worksheet("activity_log")
                    
                    row_to_add = [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "WORK", selected_task, "", "MDM Return Task"]
                    smart_append_row(log_sheet, row_to_add)
                    
                    get_activity_log.clear() 
                    time.sleep(1.0)
                    st.rerun()

        # --- 3. MASTER TASK LIST ---
        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.markdown(f"### 📋 Current Task Status")
        
        # Table data directly from CONFIG dicts (No Month included here)
        table_data = []
        for row in config_raw:
            if str(row.get('Sheet', '')).strip():
                table_data.append({
                    "Sheet": str(row.get('Sheet', '')).strip(),
                    "Work": str(row.get('Work', '')).strip(),
                    "Status": str(row.get('Status', 'Not Started')).strip()
                })

        if table_data:
            df_table = pd.DataFrame(table_data)
            def highlight_status(row):
                val = str(row['Status']).title()
                if val == 'Completed': color, text = '#dcfce7', '#166534'
                elif val == 'In Progress': color, text = '#fef08a', '#854d0e'
                else: color, text = '#fee2e2', '#991b1b'
                return [f'background-color: {color}; color: {text}; font-weight: 500'] * len(row)

            styled_df = df_table.style.apply(highlight_status, axis=1)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("No tasks configured in CONFIG sheet.")

    # ==========================================
    # TAB 2: SETTINGS & RESET
    # ==========================================
    with tab_settings:
        st.markdown("### ⚠️ Monthly Reset")
        st.write("Clicking the button below will prepare your `CONFIG` sheet for a new month.")
        st.warning(f"**Action:** All tasks in the CONFIG tab will be changed back to **'Not Started'**.")
        
        confirm = st.checkbox("I understand this will overwrite current status data in the CONFIG tab.")
        
        if st.button("🔄 Reset Status to 'Not Started'", disabled=not confirm, type="primary"):
            with st.spinner("Resetting CONFIG sheet..."):
                success = reset_mdm_config()
                if success:
                    fetch_mdm_config.clear()
                    st.success("Successfully reset all task statuses!")
                    time.sleep(1.5)
                    st.rerun()

except Exception as e:
    st.error(f"Critical System Error. Details: {e}")
