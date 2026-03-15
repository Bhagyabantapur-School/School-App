import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
from streamlit_autorefresh import st_autorefresh

# 1. Configuration & Session State Init
st.set_page_config(page_title="Live Routine", page_icon="⏱️", layout="centered")

if 'active_main_task' not in st.session_state:
    st.session_state.active_main_task = None
    st.session_state.active_sub_task = None
    st.session_state.active_start_time = None

st_autorefresh(interval=60000, key="routine_refresh")

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
    
    input[type="text"], input[type="time"], textarea {
        font-size: 16px !important;
        padding: 8px !important;
        color: #000000 !important;
    }
    
    div[data-testid="metric-container"] {
        text-align: center; 
        background-color: #f0f2f6; 
        padding: 10px; 
        border-radius: 10px; 
        margin-bottom: 15px;
    }
    
    div[data-testid="stCheckbox"] label {
        font-size: 18px !important;
        padding-top: 5px;
        padding-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Database Connection
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

@st.cache_data(ttl=60) 
def get_routine_data():
    sheet = get_sheet("routine_master")
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    
    while df.shape[1] < 7: df[df.shape[1]] = ""
    df = df.iloc[:, :7]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list"]
    df = df[df["Day"].astype(str).str.strip() != ""]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

@st.cache_data(ttl=60)
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

@st.cache_data(ttl=60)
def get_future_tasks():
    client = init_connection()
    ss = client.open("MY ROUTINE 2026")
    try:
        sheet = ss.worksheet("future_tasks")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="future_tasks", rows="100", cols="7")
        sheet.append_row(["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status"])
    
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "row_index"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 7: df[df.shape[1]] = ""
    df = df.iloc[:, :7]
    df.columns = ["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status"]
    df['row_index'] = df.index + 2 
    return df

def parse_duration_to_minutes(dur_str):
    try:
        h, m = map(int, str(dur_str).strip().split(':'))
        return (h * 60) + m
    except: return 0

def get_last_done_str(sub_task, log_df, now):
    completed_logs = log_df[log_df['End_Time'] != 'RUNNING']
    matches = completed_logs[completed_logs['Sub_Activities'].astype(str).str.strip().str.upper() == sub_task.upper()]
    if matches.empty: return "Never"
    
    max_dt = None
    for _, r in matches.iterrows():
        try:
            dt_str = f"{r['Date']} {r['End_Time']}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            if max_dt is None or dt > max_dt: max_dt = dt
        except: continue
            
    if not max_dt: return "Never"
    now_naive = now.replace(tzinfo=None)
    diff = now_naive - max_dt
    
    if diff.days > 0: return f"{diff.days}d ago"
    elif diff.seconds >= 3600: return f"{diff.seconds // 3600}h ago"
    elif diff.seconds >= 60: return f"{diff.seconds // 60}m ago"
    else: return "Just now"

try:
    df = get_routine_data()
    log_df = get_activity_log() 
    future_df = get_future_tasks()
    
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    clean_now = now.replace(second=0, microsecond=0).time()
    
    current_day = now.strftime('%A')
    today_str = now.strftime('%Y-%m-%d')
    current_time = now.time()

    tab1, tab2 = st.tabs(["⏱️ Live View", "📅 Today's Schedule"])

    # ==========================================
    # TAB 1: LIVE DASHBOARD
    # ==========================================
    with tab1:
        st.markdown(f"<h3 style='text-align: center; color: #888;'>{current_day} | {now.strftime('%I:%M %p')}</h3>", unsafe_allow_html=True)

        current_activity = "FREE TIME"
        next_activity = "NONE"
        next_time_str = ""
        current_sub_activities = ""
        current_check_list = ""

        today_schedule = df[df['Day'].str.strip() == current_day].to_dict('records')

        for i, row in enumerate(today_schedule):
            try:
                start_str = str(row['Start_Time']).strip()
                end_str = str(row['End_Time']).strip()
                
                start_t = datetime.strptime(start_str, '%H:%M').time()
                if end_str == '0:00': end_t = datetime.strptime('23:59:59', '%H:%M:%S').time()
                else: end_t = datetime.strptime(end_str, '%H:%M').time()

                if start_t <= current_time <= end_t:
                    current_activity = str(row['Activity']).strip().upper()
                    current_sub_activities = str(row.get('Sub_Activities', '')).strip()
                    current_check_list = str(row.get('check_list', '')).strip()
                    
                    if i + 1 < len(today_schedule):
                        next_row = today_schedule[i+1]
                        next_activity = str(next_row['Activity']).strip().upper()
                        next_time_str = datetime.strptime(str(next_row['Start_Time']).strip(), '%H:%M').strftime('%I:%M %p')
                    else: next_activity = "END OF DAY"
                    break
                    
                elif current_time < start_t and current_activity == "FREE TIME":
                    next_activity = str(row['Activity']).strip().upper()
                    next_time_str = datetime.strptime(start_str, '%H:%M').strftime('%I:%M %p')
                    break
            except ValueError: continue

        if current_activity in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY"]: color = "#ff4b4b" 
        elif current_activity in ["WORK", "REPORT", "TASK"]: color = "#0068c9" 
        elif current_activity == "HEALTH": color = "#2e7b32" 
        elif current_activity in ["SLEEP", "PRE", "TEA", "OUT"]: color = "#ff9f36" 
        else: color = "#333333" 

        st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 30px; margin-bottom: 10px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

        if next_activity not in ["NONE", "END OF DAY"]:
            st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: <b>{next_activity}</b> at {next_time_str}</h4>", unsafe_allow_html=True)
        elif next_activity == "END OF DAY":
            st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: Schedule Complete</h4>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # --- SMART SCHEDULE INJECTION & COUNTDOWN ---
        sub_list = [s.strip() for s in current_sub_activities.split(',') if s.strip()]
        chk_list = [c.strip() for c in current_check_list.split(',') if c.strip()]
        all_logged_items = log_df['check_list'].tolist() + log_df['Sub_Activities'].tolist()
        
        upcoming_ui_elements = []

        if not future_df.empty:
            for _, r in future_df.iterrows():
                try:
                    due_dt_str = f"{r['Due_Date']} {r['Due_Time']}"
                    due_dt = ist_timezone.localize(datetime.strptime(due_dt_str, "%Y-%m-%d %H:%M"))
                    time_diff = due_dt - now
                    hours_until_due = time_diff.total_seconds() / 3600
                    
                    formatted_task = f"{r['Task_Name']} [Due: {r['Due_Date'][5:]} {r['Due_Time']}]"
                    
                    is_done_in_sheet = str(r['Status']).strip().upper() == 'COMPLETED'
                    is_done_in_log = any(formatted_task.upper() == str(x).strip().upper() for x in all_logged_items)
                    is_done = is_done_in_sheet or is_done_in_log
                    
                    # RULE 1: If it's done, skip it entirely so it disappears from the screen!
                    if is_done: continue
                        
                    # RULE 2: If < 24h away but NOT DUE YET -> Put in Top Countdown Box
                    if 0 < hours_until_due <= 24:
                        h, rem = divmod(int(time_diff.total_seconds()), 3600)
                        m = rem // 60
                        time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
                        upcoming_ui_elements.append(f"**{r['Task_Name']}** ({r['Activity']}) due in **{time_str}**")
                        
                    # RULE 3: If exact due time is reached (<= 0h) -> Drop into actionable lists
                    elif hours_until_due <= 0 and str(r['Activity']).strip().upper() == current_activity:
                        if r['Type'] == 'Sub-Activity': sub_list.append(formatted_task)
                        elif r['Type'] == 'Checklist': chk_list.append(formatted_task)
                except: continue

        # --- RENDER TOP COUNTDOWN BOX ---
        if upcoming_ui_elements:
            st.markdown("<div style='background-color:#fff3e0; padding:15px; border-radius:10px; border: 1px solid #ffcc80;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: center; color: #e65100; margin-top:0; margin-bottom:15px;'>⏳ Upcoming Tasks (Next 24h)</h4>", unsafe_allow_html=True)
            for element in upcoming_ui_elements:
                st.markdown(f"<p style='text-align: center; margin-bottom:5px; font-size:16px; color: #d84315;'>{element}</p>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # --- CHECKLIST FEATURE ---
        if chk_list:
            st.markdown("---")
            st.markdown("<h4 style='text-align: center; color: #333;'>✅ Tasks & Reminders</h4>", unsafe_allow_html=True)
            
            today_logs = log_df[log_df['Date'] == today_str]
            today_logged_tasks = today_logs[today_logs['Activity'] == current_activity]['check_list'].tolist()
            
            for task in chk_list:
                # If it's a dynamic future task, it's strictly not done (otherwise it would be filtered out above)
                if "[Due:" in task:
                    is_done = False
                else:
                    is_done = any(task.upper() == str(x).strip().upper() for x in today_logged_tasks)
                    
                checked = st.checkbox(task, value=is_done, disabled=is_done, key=f"chk_{task}_{current_activity}")
                
                if checked and not is_done:
                    sheet_log = get_sheet("activity_log")
                    sheet_log.append_row([
                        today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), 
                        "0:00", current_activity, "", task, "Checked off"
                    ])
                    
                    if "[Due:" in task:
                        raw_task = task.split(" [Due:")[0].strip()
                        matches = future_df[(future_df['Task_Name'].str.strip() == raw_task) & (future_df['Type'] == 'Checklist')]
                        if not matches.empty:
                            r_idx = int(matches.iloc[0]['row_index'])
                            fsheet = get_sheet("future_tasks")
                            fsheet.update_cell(r_idx, 7, "Completed") 
                            
                    st.cache_data.clear()
                    st.rerun()

        # --- BULLETPROOF GOOGLE SHEETS TRACKER ---
        running_tasks = log_df[log_df['End_Time'] == 'RUNNING']
        is_running = not running_tasks.empty
        
        if sub_list or is_running:
            st.markdown("---")
            st.markdown("<h4 style='text-align: center; color: #333;'>Tap to Track Activity</h4>", unsafe_allow_html=True)
            
            if is_running:
                active_row = running_tasks.iloc[-1]
                active_main = str(active_row['Activity'])
                active_sub = str(active_row['Sub_Activities'])
                display_name = active_sub if active_sub else active_main
                
                try:
                    start_dt_str = f"{active_row['Date']} {active_row['Start_Time']}"
                    dt_naive = datetime.strptime(start_dt_str, "%Y-%m-%d %H:%M")
                    active_start_time = ist_timezone.localize(dt_naive)
                    elapsed_time = now - active_start_time
                    mins_elapsed = int(elapsed_time.total_seconds() // 60)
                except:
                    mins_elapsed = 0 
                
                st.info(f"⏳ **In Progress:** {display_name} (Running for {mins_elapsed} min)")
                
                col_stop, col_cancel = st.columns(2)
                with col_stop:
                    if st.button("🛑 SAVE", use_container_width=True, type="primary"):
                        end_time_log = now.time()
                        try:
                            hours, remainder = divmod(int(elapsed_time.total_seconds()), 3600)
                            minutes = remainder // 60
                            duration_str = f"{hours}:{minutes:02d}"
                        except: duration_str = "0:00"

                        log_sheet = get_sheet("activity_log")
                        cells = log_sheet.findall("RUNNING")
                        for cell in cells:
                            if cell.col == 3: 
                                target_row = cell.row
                                log_sheet.update_cell(target_row, 3, end_time_log.strftime('%H:%M')) 
                                log_sheet.update_cell(target_row, 4, duration_str)                   
                                log_sheet.update_cell(target_row, 8, "Auto-logged via Timer") 
                                break
                                
                        if "[Due:" in active_sub:
                            raw_task = active_sub.split(" [Due:")[0].strip()
                            matches = future_df[(future_df['Task_Name'].str.strip() == raw_task) & (future_df['Type'] == 'Sub-Activity')]
                            if not matches.empty:
                                r_idx = int(matches.iloc[0]['row_index'])
                                fsheet = get_sheet("future_tasks")
                                fsheet.update_cell(r_idx, 7, "Completed") 
                        
                        st.cache_data.clear()
                        st.success("Activity saved!")
                        time.sleep(1)
                        st.rerun()

                with col_cancel:
                    if st.button("❌ CANCEL", use_container_width=True):
                        log_sheet = get_sheet("activity_log")
                        cells = log_sheet.findall("RUNNING")
                        for cell in cells:
                            if cell.col == 3: 
                                log_sheet.delete_rows(cell.row)
                                break
                        st.cache_data.clear()
                        st.warning("Activity cancelled.")
                        time.sleep(1)
                        st.rerun()

            elif sub_list:
                cols = st.columns(3)
                for idx, task in enumerate(sub_list):
                    with cols[idx % 3]:
                        last_done = get_last_done_str(task, log_df, now)
                        # Hide Last Done if it's a one-off future task
                        last_txt = f"\n(Last: {last_done})" if "[Due:" not in task else ""
                        
                        if st.button(f"▶️ {task}{last_txt}", key=f"btn_{task}", use_container_width=True):
                            log_sheet = get_sheet("activity_log")
                            log_sheet.append_row([
                                today_str, now.strftime('%H:%M'), "RUNNING", "RUNNING",    
                                current_activity, task, "", "In Progress"
                            ])
                            st.cache_data.clear()
                            st.rerun()

        st.markdown("---")
        
        # Today's Productivity Metrics
        st.markdown("<h4 style='text-align: center; color: #555; margin-bottom: 20px;'>📊 Today's Actual Productivity</h4>", unsafe_allow_html=True)
        today_logs = log_df[(log_df['Date'] == today_str) & (log_df['Duration'] != 'RUNNING')].copy()
        
        if not today_logs.empty:
            today_logs['Total_Minutes'] = today_logs['Duration'].apply(parse_duration_to_minutes)
            summary = today_logs.groupby('Activity')['Total_Minutes'].sum().sort_values(ascending=False)
            cols = st.columns(min(len(summary), 3))
            col_idx = 0
            for act, total_mins in summary.items():
                hours, remainder_mins = divmod(total_mins, 60)
                display_time = f"{int(hours)}:{int(remainder_mins):02d}"
                with cols[col_idx % 3]:
                    st.metric(label=act, value=display_time)
                col_idx += 1
        else:
            st.markdown("<p style='text-align: center; color: #888;'>No completed activities logged yet.</p>", unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- FUTURE SCHEDULER FORM ---
        with st.expander("🗓️ Schedule Future Task"):
            with st.form("schedule_future_form", clear_on_submit=True):
                st.markdown("### Attach Task to a Future Activity")
                
                unique_activities = [act for act in df['Activity'].unique() if act.strip()]
                f_act = st.selectbox("Parent Category", unique_activities, key="f_act")
                f_type = st.radio("Task Type", ["Checklist", "Sub-Activity"], horizontal=True, key="f_type")
                f_entity = st.selectbox("Entity", ["Personal", "School", "People"], key="f_entity")
                f_name = st.text_input("Task Details", placeholder="e.g., Pay Electricity Bill", key="f_name")
                
                col1, col2 = st.columns(2)
                with col1: f_date = st.date_input("Due Date", value=now.date(), key="f_date")
                with col2: f_time = st.time_input("Due Time", value=clean_now, key="f_time")
                    
                if st.form_submit_button("Schedule Task", use_container_width=True):
                    if f_name:
                        client = init_connection()
                        ss = client.open("MY ROUTINE 2026")
                        try:
                            fsheet = ss.worksheet("future_tasks")
                        except gspread.exceptions.WorksheetNotFound:
                            fsheet = ss.add_worksheet(title="future_tasks", rows="100", cols="7")
                            fsheet.append_row(["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status"])
                        
                        fsheet.append_row([
                            f_date.strftime('%Y-%m-%d'),
                            f_time.strftime('%H:%M'),
                            f_act.upper().strip(),
                            f_type,
                            f_name.strip(),
                            f_entity,
                            "Pending"
                        ])
                        st.cache_data.clear()
                        st.success("Task Scheduled! It will appear 24 hours before due time.")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Please enter task details.")

        # Manual Log Form
        with st.expander("📝 Manual Log Activity"):
            with st.form("log_activity_form", clear_on_submit=True):
                st.markdown("### Manually Record Time")
                log_date = st.date_input("Date", value=now.date(), key="log_date")
                col_act1, col_act2 = st.columns(2)
                with col_act1: log_activity = st.text_input("Main Category", value=current_activity if current_activity != "FREE TIME" else "", key="log_act")
                with col_act2: log_sub_activity = st.text_input("Sub-Activity", placeholder="e.g., YOGA", key="log_sub")
                    
                col1, col2 = st.columns(2)
                with col1: log_start = st.time_input("Started At", value=clean_now, key="log_start")
                with col2: log_end = st.time_input("Ended At", value=clean_now, key="log_end")
                
                log_chk = st.text_input("Checklist Item (Optional)", key="log_chk")    
                log_notes = st.text_area("Notes", key="log_notes")
                
                if st.form_submit_button("Save to Activity Log", use_container_width=True):
                    if log_activity:
                        start_dt = datetime.combine(log_date, log_start)
                        end_dt = datetime.combine(log_date, log_end)
                        if end_dt < start_dt: end_dt = end_dt.replace(day=end_dt.day + 1)
                        duration_td = end_dt - start_dt
                        h, m = divmod(duration_td.seconds, 3600)
                        
                        sheet_log = get_sheet("activity_log")
                        sheet_log.append_row([
                            log_date.strftime('%Y-%m-%d'), log_start.strftime('%H:%M'), log_end.strftime('%H:%M'), 
                            f"{h}:{m//60:02d}", log_activity.upper().strip(), log_sub_activity.upper().strip(),
                            log_chk.strip(), log_notes
                        ])
                        st.cache_data.clear()
                        st.success("Activity logged!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Please enter a Main Category.")

    # ==========================================
    # TAB 2: LIVE SPREADSHEET EDITOR
    # ==========================================
    with tab2:
        st.markdown(f"<h3 style='text-align: center; color: #555; margin-bottom: 5px;'>{current_day}'s Full Routine</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888; font-size: 14px; margin-bottom: 20px;'>Tap any cell to edit. Scroll right to see Sub-Activities and Checklists.</p>", unsafe_allow_html=True)
        
        today_full_df = df[df['Day'].str.strip() == current_day].copy()
        
        if not today_full_df.empty:
            edit_df = today_full_df[['Start_Time', 'End_Time', 'Activity', 'Sub_Activities', 'check_list']].copy()
            
            def convert_to_time(t_str):
                try:
                    if t_str.strip() == '0:00': return datetime.strptime('00:00', '%H:%M').time()
                    return datetime.strptime(t_str.strip(), '%H:%M').time()
                except: return datetime.strptime('00:00', '%H:%M').time()

            edit_df['Start_Time'] = edit_df['Start_Time'].apply(convert_to_time)
            edit_df['End_Time'] = edit_df['End_Time'].apply(convert_to_time)
            
            edited_schedule = st.data_editor(
                edit_df,
                column_config={
                    "Start_Time": st.column_config.TimeColumn("Start", format="HH:mm", step=60, required=True),
                    "End_Time": st.column_config.TimeColumn("End", format="HH:mm", step=60, required=True),
                    "Activity": st.column_config.TextColumn("Activity", required=True),
                    "Sub_Activities": st.column_config.TextColumn("Sub List (comma sep.)"),
                    "check_list": st.column_config.TextColumn("Checklist (comma sep.)")
                },
                hide_index=True,
                use_container_width=True,
                num_rows="dynamic",
                key="schedule_editor"
            )
            
            if st.button("💾 Save Changes to Google Sheet", use_container_width=True):
                with st.spinner("Syncing to Google Sheets..."):
                    new_rows = []
                    for _, row in edited_schedule.iterrows():
                        if pd.isna(row['Activity']) or str(row['Activity']).strip() == "": continue
                        start_t, end_t = row['Start_Time'], row['End_Time']
                        if pd.isna(start_t) or pd.isna(end_t): continue
                            
                        start_str = start_t.strftime('%H:%M')
                        end_str = end_t.strftime('%H:%M')
                        s_dt = datetime.combine(now.date(), start_t)
                        e_dt = datetime.combine(now.date(), end_t)
                        
                        if end_str in ['00:00', '0:00'] or e_dt < s_dt:
                            e_dt = e_dt.replace(day=e_dt.day + 1)
                            
                        duration_td = e_dt - s_dt
                        h, m = divmod(duration_td.seconds, 3600)
                        duration_str = f"{h}:{m//60:02d}"
                        
                        sub_act = str(row.get('Sub_Activities', '')).strip()
                        if sub_act == 'nan': sub_act = ""
                        chk_act = str(row.get('check_list', '')).strip()
                        if chk_act == 'nan': chk_act = ""
                        
                        new_rows.append([current_day, start_str, end_str, duration_str, str(row['Activity']).strip().upper(), sub_act, chk_act])

                    full_df = df.copy()
                    other_days_df = full_df[full_df['Day'].str.strip() != current_day]
                    new_today_df = pd.DataFrame(new_rows, columns=["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list"])
                    final_df = pd.concat([other_days_df, new_today_df], ignore_index=True)
                    
                    routine_sheet = get_sheet("routine_master")
                    routine_sheet.clear() 
                    data_to_upload = [final_df.columns.values.tolist()] + final_df.values.tolist()
                    routine_sheet.update(values=data_to_upload, range_name="A1")
                    
                    st.cache_data.clear()
                    st.success("Schedule successfully updated!")
                    time.sleep(1)
                    st.rerun()

            st.markdown("---")
            st.markdown("<h4 style='text-align: center; color: #555; margin-bottom: 20px;'>📈 Scheduled Summary</h4>", unsafe_allow_html=True)
            today_full_df['Total_Minutes'] = today_full_df['Duration'].apply(parse_duration_to_minutes)
            schedule_summary = today_full_df.groupby('Activity')['Total_Minutes'].sum().sort_values(ascending=False)
            cols_sched = st.columns(min(len(schedule_summary), 3))
            col_idx_sched = 0
            for act, total_mins in schedule_summary.items():
                hours, remainder_mins = divmod(total_mins, 60)
                display_time = f"{int(hours)}:{int(remainder_mins):02d}"
                with cols_sched[col_idx_sched % 3]:
                    st.metric(label=act, value=display_time)
                col_idx_sched += 1
        else:
            st.info(f"No routine scheduled for {current_day}.")
            
except Exception as e:
    st.error(f"System Error: {e}")
