import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("dashboard.py") 
st.write("---") 
# -------------------
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

# ==========================================
# 1. Configuration & Styling
# ==========================================
st.set_page_config(page_title="Monthly Tasks", page_icon="📆", layout="wide")

# Track Pomodoro states for audio beeps & setup auto-refresh
if 'pomodoro_state' not in st.session_state:
    st.session_state.pomodoro_state = {}

# Refresh every 2 minutes for the timer
st_autorefresh(interval=120000, key="monthly_refresh")

# Master Formula for Activity Log
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

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

@st.cache_resource
def get_main_spreadsheet():
    client = init_connection()
    return client.open("MY ROUTINE 2026")

def get_sheet(tab_name):
    ss = get_main_spreadsheet()
    return ss.worksheet(tab_name)

@st.cache_data(ttl=300)
def get_monthly_tasks():
    ss = get_main_spreadsheet()
    try:
        sheet = ss.worksheet("monthly_tasks")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="monthly_tasks", rows="100", cols="4")
        sheet.append_row(["Task Name", "Category", "Target Day", "Last_Done_Date"])
        
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Task Name", "Category", "Target Day", "Last_Done_Date", "row_index"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 4: df[df.shape[1]] = ""
    df = df.iloc[:, :4]
    df.columns = ["Task Name", "Category", "Target Day", "Last_Done_Date"]
    df['row_index'] = df.index + 2 
    return df

@st.cache_data(ttl=300)
def get_activity_log():
    sheet = get_sheet("activity_log")
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Category", "Task_Name", "Checklist", "Notes", "row_index"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Category", "Task_Name", "Checklist", "Notes"]
    df['row_index'] = df.index + 2 # Keep track of row for updating RUNNING tasks
    return df

# ==========================================
# 3. Main Dashboard Logic
# ==========================================
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)
current_month_prefix = now.strftime('%Y-%m') # e.g., "2026-04"
current_day = now.day
today_str = now.strftime('%Y-%m-%d')
current_time_str = now.strftime('%H:%M')

col1, col2 = st.columns([5, 1])
with col1:
    st.title("📆 Monthly Recurring Tasks")
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Sync", use_container_width=True):
        get_monthly_tasks.clear()
        get_activity_log.clear()
        st.toast("Synced with Google Sheets!")
        time.sleep(0.5)
        st.rerun()

try:
    df_tasks = get_monthly_tasks()
    log_df = get_activity_log()
    running_tasks = log_df[log_df['End_Time'] == 'RUNNING'] if not log_df.empty else pd.DataFrame()
    
    # --- SETUP TABS ---
    tab_current, tab_history = st.tabs(["📋 Current Month", "🕰️ History"])

    with tab_current:
        if not df_tasks.empty:
            # --- DATA PROCESSING ---
            def check_status(row):
                last_done = str(row['Last_Done_Date']).strip()
                target_day_str = str(row['Target Day']).strip()
                
                try: target_day = int(target_day_str)
                except: target_day = 31
                
                if last_done.startswith(current_month_prefix):
                    return "Completed", "#2e7b32" # Green
                elif current_day > target_day:
                    return "Overdue", "#d32f2f" # Red
                else:
                    return "Pending", "#f57c00" # Orange

            df_tasks[['Status', 'Color']] = df_tasks.apply(check_status, axis=1, result_type='expand')
            
            completed_tasks = df_tasks[df_tasks['Status'] == 'Completed']
            pending_tasks = df_tasks[df_tasks['Status'].isin(['Pending', 'Overdue'])].copy()
            
            # Sort pending by Target Day
            pending_tasks['Target Day Num'] = pd.to_numeric(pending_tasks['Target Day'], errors='coerce').fillna(31)
            pending_tasks = pending_tasks.sort_values('Target Day Num')
            
            # --- METRICS ---
            total = len(df_tasks)
            done = len(completed_tasks)
            progress = done / total if total > 0 else 0
            
            st.markdown(f"### Progress for {now.strftime('%B %Y')}")
            st.progress(progress)
            st.markdown(f"<p style='text-align: right; color: #666;'>{done} of {total} tasks completed</p>", unsafe_allow_html=True)
            st.markdown("---")

            # --- PENDING TASKS SECTION ---
            st.markdown("<h4 style='color: #d84315;'>⏳ Action Required This Month</h4>", unsafe_allow_html=True)
            
            if pending_tasks.empty:
                st.success("🎉 All monthly tasks are complete! Great job!")
            else:
                for idx, row in pending_tasks.iterrows():
                    bg_color = "#fff3e0" if row['Status'] == 'Pending' else "#ffebee"
                    border_color = row['Color']
                    day_text = f"Target: {row['Target Day']}th" if str(row['Target Day']).strip() else "No specific date"
                    task_name = row['Task Name']
                    cat = row['Category'].upper() if row['Category'] else "WORK"
                    
                    # Check if this task is currently running in the Activity Log
                    is_running = False
                    sheet_row = None
                    if not running_tasks.empty:
                        running_match = running_tasks[(running_tasks['Task_Name'] == task_name) & (running_tasks['Category'] == cat)]
                        if not running_match.empty:
                            is_running = True
                            active_row = running_match.iloc[-1]
                            sheet_row = active_row['row_index']

                    # Update display status if the task is actively running
                    display_status = "In Progress" if is_running else row['Status']
                    status_color = "#0068c9" if is_running else border_color # Blue if running

                    if is_running:
                        # ==========================================
                        # POMODORO TIMER UI (Task is Running)
                        # ==========================================
                        st.markdown(f"""
                        <div style='background-color: {bg_color}; border-left: 5px solid {border_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px;'>
                            <strong style='font-size: 16px; color: #333;'>{task_name}</strong> 
                            <span style='color: {status_color}; font-weight: bold; font-size: 12px; margin-left: 10px;'>[{display_status}]</span><br>
                            <span style='color: #666; font-size: 14px;'>Category: {cat} | {day_text}</span>
                        </div>
                        """, unsafe_allow_html=True)

                        # Calculate elapsed time
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
                        task_id = f"mtask_{sheet_row}"
                        
                        # Beep Logic
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
                            <div style='margin-top: 4px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;'>
                                <span style='color: {p_color}; font-weight: bold; font-size: 14px;'>{p_state} (Cycle {pomodoro_count})</span>
                                <span style='color: #555; font-size: 13px; font-weight: bold;'>{p_left}m left (Total: {mins_elapsed}m)</span>
                            </div>
                            <div style='width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 6px;'>
                                <div style='width: {p_prog * 100}%; background-color: {p_color}; height: 6px; border-radius: 4px; transition: width 0.5s ease;'></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        col_stop, col_cancel = st.columns(2)
                        with col_stop:
                            if st.button("🛑 FINISH & MARK DONE", key=f"save_{row['row_index']}", use_container_width=True, type="primary"):
                                log_sheet = get_sheet("activity_log")
                                log_sheet.update_cell(sheet_row, 3, current_time_str) 
                                log_sheet.update_cell(sheet_row, 4, GS_FORMULA) 
                                
                                m_sheet = get_sheet("monthly_tasks")
                                m_sheet.update_cell(row['row_index'], 4, today_str)

                                get_monthly_tasks.clear()
                                get_activity_log.clear()
                                st.success(f"Finished & Logged '{task_name}'!")
                                time.sleep(1)
                                st.rerun()

                        with col_cancel:
                            if st.button("❌ CANCEL TIMER", key=f"cancel_{row['row_index']}", use_container_width=True):
                                log_sheet = get_sheet("activity_log")
                                log_sheet.delete_rows(int(sheet_row))
                                get_activity_log.clear()
                                st.warning(f"Timer Cancelled for '{task_name}'")
                                time.sleep(1)
                                st.rerun()
                                
                    else:
                        # ==========================================
                        # STANDARD UI (Task Not Running)
                        # ==========================================
                        col_info, col_btns = st.columns([3, 2])
                        
                        with col_info:
                            st.markdown(f"""
                            <div style='background-color: {bg_color}; border-left: 5px solid {border_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px;'>
                                <strong style='font-size: 16px; color: #333;'>{task_name}</strong> 
                                <span style='color: {status_color}; font-weight: bold; font-size: 12px; margin-left: 10px;'>[{display_status}]</span><br>
                                <span style='color: #666; font-size: 14px;'>Category: {cat} | {day_text}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        with col_btns:
                            st.markdown("<br>", unsafe_allow_html=True)
                            # Start Timer button now takes the full width of the column
                            if st.button("▶️ Start Timer", key=f"start_{row['row_index']}", use_container_width=True):
                                log_sheet = get_sheet("activity_log")
                                log_sheet.append_row([
                                    today_str, current_time_str, "RUNNING", GS_FORMULA, 
                                    cat, task_name, "", "Monthly Task Tracking"
                                ], value_input_option="USER_ENTERED")
                                
                                get_activity_log.clear()
                                st.success(f"Started Timer for '{task_name}'!")
                                time.sleep(1)
                                st.rerun()
                                    
            st.markdown("<br>", unsafe_allow_html=True)

            # --- COMPLETED TASKS SECTION ---
            with st.expander(f"✅ Completed This Month ({done})", expanded=False):
                if completed_tasks.empty:
                    st.info("No tasks completed yet this month.")
                else:
                    for idx, row in completed_tasks.iterrows():
                        st.markdown(f"""
                        <div style='background-color: #e8f5e9; border-left: 5px solid #2e7b32; padding: 10px; border-radius: 6px; margin-bottom: 8px;'>
                            <strong style='font-size: 15px; color: #333;'>{row['Task Name']}</strong><br>
                            <span style='color: #2e7b32; font-size: 13px;'>Completed on: {row['Last_Done_Date']}</span>
                        </div>
                        """, unsafe_allow_html=True)

        else:
            st.info("No monthly tasks setup yet. Add your first one below!")

        st.markdown("---")

        # ==========================================
        # 4. Add New Task Form
        # ==========================================
        with st.expander("➕ Add New Monthly Recurring Task"):
            with st.form("add_monthly_task", clear_on_submit=True):
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    new_task = st.text_input("Task Name", placeholder="e.g. Server Backup")
                with col_t2:
                    new_cat = st.selectbox("Category", ["WORK", "HOME", "FINANCE", "HEALTH", "SCHOOL", "YOUTUBE"])
                    
                new_target = st.number_input("Target Day of Month (1-31)", min_value=1, max_value=31, value=15)
                
                if st.form_submit_button("Save Recurring Task", type="primary", use_container_width=True):
                    if new_task:
                        sheet = get_sheet("monthly_tasks")
                        sheet.append_row([new_task.strip(), new_cat, new_target, ""])
                        get_monthly_tasks.clear()
                        st.success("Monthly task added successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Please enter a Task Name.")

    # ==========================================
    # TAB 2: HISTORY 
    # ==========================================
    with tab_history:
        st.markdown("<h3 style='color: #555;'>🕰️ Past Monthly Activity</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #888;'>A chronological log of all the monthly recurring tasks you have completed.</p>", unsafe_allow_html=True)
        
        if not log_df.empty:
            # Filter logs to only show Monthly Tasks (looking for keywords we use in Notes)
            history_df = log_df[log_df['Notes'].astype(str).str.contains("Monthly Task", case=False, na=False)].copy()
            
            # Filter out tasks that are currently "RUNNING"
            history_df = history_df[history_df['End_Time'] != "RUNNING"]

            if not history_df.empty:
                # Convert date string to actual datetime for sorting and grouping
                history_df['Date_dt'] = pd.to_datetime(history_df['Date'], errors='coerce')
                
                # Sort from newest to oldest
                history_df = history_df.dropna(subset=['Date_dt']).sort_values(['Date_dt', 'End_Time'], ascending=[False, False])
                
                # Create a Month-Year column (e.g., "May 2026")
                history_df['Month_Year'] = history_df['Date_dt'].dt.strftime('%B %Y')
                
                # Get unique months to iterate through
                unique_months = history_df['Month_Year'].unique()
                
                for month in unique_months:
                    st.markdown(f"#### 📅 {month}")
                    
                    month_data = history_df[history_df['Month_Year'] == month]
                    
                    for _, row in month_data.iterrows():
                        dur_str = f"| Duration: {row['Duration']}" if row['Duration'] else ""
                        
                        st.markdown(f"""
                        <div style='background-color: #fafafa; border-left: 4px solid #9e9e9e; padding: 12px; margin-bottom: 8px; border-radius: 4px; border-top: 1px solid #eee; border-right: 1px solid #eee; border-bottom: 1px solid #eee;'>
                            <strong style='color: #333; font-size: 16px;'>{row['Task_Name']}</strong> 
                            <span style='color: #0068c9; font-size: 13px; margin-left: 5px; font-weight: bold;'>[{row['Category']}]</span><br>
                            <span style='color: #666; font-size: 14px;'>✅ Finished on <b>{row['Date']}</b> at <b>{row['End_Time']}</b> {dur_str}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    st.markdown("<hr style='margin-top: 15px; margin-bottom: 20px; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)
            else:
                st.info("You haven't completed any monthly tasks yet to show in the history!")
        else:
            st.info("Your activity log is currently empty.")

except Exception as e:
    st.error(f"System Error: {e}")
