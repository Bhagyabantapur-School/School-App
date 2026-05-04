import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

# --- Master Google Sheets Formula for Duration ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

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
    
    /* Mobile specific adjustments */
    @media (max-width: 640px) {
        .stHeadingContainer h1 {
            font-size: 1.8rem !important;
        }
        div.stButton > button {
            margin-top: 5px;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Database Connection & Helpers
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
    """Safely appends a row by finding the true end of Column A, avoiding formatting bugs."""
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
def get_mdm_tasks():
    try:
        ss = get_mdm_spreadsheet()
        config_sheet = ss.worksheet("CONFIG")
        config_data = config_sheet.get_all_records()
        
        tasks = []
        for row in config_data:
            sheet_val = str(row.get('Sheet', '')).strip()
            work_val = str(row.get('Work', '')).strip()
            if sheet_val or work_val: 
                tasks.append(f"{sheet_val} | {work_val}")
                
        if not tasks:
            return ["No tasks found in CONFIG sheet"]
        return tasks
    except Exception as e:
        st.error(f"Failed to read CONFIG sheet: {e}")
        return ["Error loading tasks"]

# ==========================================
# 3. Main Application Logic
# ==========================================
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)
today_str = now.strftime('%Y-%m-%d')
mdm_date_str = now.strftime('%d-%b-%Y') # Specific format for MDM sheet

try:
    log_df = get_activity_log()
    mdm_tasks_list = get_mdm_tasks()
    
    # Filter for currently running MDM Tasks
    # We identify MDM tasks in the routine tracker by looking for the specific Note
    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Notes'] == 'MDM Return Task')]
    active_count = len(running_tasks)

    # --- HEADER & SYNC ---
    st.title("📦 MDM Return Logger")
    
    if st.button("🔄 Sync Data", use_container_width=True):
        get_activity_log.clear()
        get_mdm_tasks.clear()
        st.toast("Synced with Google Sheets!")
        time.sleep(1.0)
        st.rerun()
        
    st.markdown("---")

    # --- FLOATING ACTIVE BADGE ---
    if active_count > 0:
        st.markdown(f"""
            <div style='position: fixed; bottom: 30px; left: 20px; background-color: #0068c9; color: white; padding: 8px 16px; border-radius: 20px; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); font-weight: bold; font-size: 16px; z-index: 9999; pointer-events: none; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 16px; margin-right: 6px; animation: pulse 1.5s infinite;'>⏱️</span> MDM Task Active
            </div>
        """, unsafe_allow_html=True)

    with st.container():
        
        # 1. RENDER RUNNING MDM TASKS
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
                
                # Pomodoro Logic
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
                    p_color = "#0068c9" # Blue for Work
                    p_left = 25 - cycle_minute
                    p_prog = cycle_minute / 25.0
                else:
                    p_state = "☕ Rest"
                    p_color = "#2e7b32" # Green for Break
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
                
                col_stop, col_cancel = st.columns([1, 1])
                with col_stop:
                    if st.button("🛑 STOP & LOG", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                        end_time_log = now.strftime('%H:%M')
                        
                        # 1. Update Routine App Master Log
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.update_cell(sheet_row, 3, end_time_log) 
                        log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                        
                        # 2. Extract specific MDM data for the MDM Log
                        parts = display_name.split(" | ", 1)
                        sheet_name = parts[0] if len(parts) > 0 else ""
                        work_name = parts[1] if len(parts) > 1 else ""
                        
                        start_str = active_row['Start_Time']
                        
                        # Calculate static duration string for the MDM log specifically
                        h, m = divmod(mins_elapsed, 60)
                        duration_str = f"{h}:{m:02d}"
                        
                        row_data = [sheet_name, work_name, mdm_date_str, start_str, end_time_log, duration_str]
                        
                        # 3. Append to MDM Log
                        try:
                            mdm_ss = get_mdm_spreadsheet()
                            mdm_target_sheet = mdm_ss.get_worksheet(0) # First tab
                            smart_append_row(mdm_target_sheet, row_data)
                            
                            # Targeted clear
                            get_activity_log.clear() 
                            st.success(f"Saved: Task logged to both databases!")
                            time.sleep(1.0)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to log details to MDM LOG: {e}")

                with col_cancel:
                    if st.button("❌ CANCEL", key=f"cancel_{sheet_row}", use_container_width=True):
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.delete_rows(sheet_row)
                        
                        get_activity_log.clear() 
                        st.warning(f"Cancelled")
                        time.sleep(1.0)
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        # 2. START NEW TASK UI
        if active_count == 0:
            st.markdown("<div style='margin-bottom: 5px; color: #0068c9;'><b>🚀 Start New MDM Task:</b></div>", unsafe_allow_html=True)
            
            selected_task = st.selectbox("Select Task from Config", mdm_tasks_list, key="start_mdm_sel")
            
            st.markdown(
                """
                <div id="mdm_start_anchor"></div>
                <style>
                div.element-container:has(#mdm_start_anchor) + div.element-container button {
                    background-color: #0068c9 !important; 
                    color: white !important;
                    border: none !important;
                    margin-top: 10px;
                }
                div.element-container:has(#mdm_start_anchor) + div.element-container button:hover {
                    background-color: #005bb5 !important; 
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            
            if st.button("▶️ Start Task", key="start_mdm_btn", use_container_width=True):
                if selected_task in ["No tasks found in CONFIG sheet", "Error loading tasks"]:
                    st.error("Cannot start without valid tasks from CONFIG tab.")
                else:
                    main_ss = get_main_spreadsheet()
                    log_sheet = main_ss.worksheet("activity_log")
                    
                    # Appends a RUNNING row to Routine Master activity_log
                    row_to_add = [
                        today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                        "WORK", selected_task, "", "MDM Return Task"
                    ]
                    smart_append_row(log_sheet, row_to_add)
                    
                    get_activity_log.clear() 
                    time.sleep(1.0)
                    st.rerun()

except Exception as e:
    st.error(f"Critical System Error: Make sure your spreadsheets exist and are shared. Details: {e}")
