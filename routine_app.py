import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# --- Master Google Sheets Formula for Duration ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

# 1. Configuration & Session State Init
st.set_page_config(page_title="Live Routine", page_icon="⏱️", layout="centered")

if 'active_main_task' not in st.session_state:
    st.session_state.active_main_task = None
    st.session_state.active_sub_task = None
    st.session_state.active_start_time = None

# Track Pomodoro states for audio beeps
if 'pomodoro_state' not in st.session_state:
    st.session_state.pomodoro_state = {}

st_autorefresh(interval=120000, key="routine_refresh")

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
    
    /* CSS for the pulsing dot animation */
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.9; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.9; }
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

@st.cache_data(ttl=300) 
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

@st.cache_data(ttl=300)
def get_future_tasks():
    client = init_connection()
    ss = client.open("MY ROUTINE 2026")
    try:
        sheet = ss.worksheet("future_tasks")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="future_tasks", rows="100", cols="8")
        sheet.append_row(["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "Cancel_Reason"])
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "Cancel_Reason", "row_index"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "Cancel_Reason"]
    df['row_index'] = df.index + 2 
    return df

@st.cache_data(ttl=300)
def get_water_log():
    client = init_connection()
    ss = client.open("MY ROUTINE 2026")
    try:
        sheet = ss.worksheet("water_log")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="water_log", rows="1000", cols="3")
        sheet.append_row(["Date", "Time", "Amount_ml"])
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Time", "Amount_ml"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 3: df[df.shape[1]] = ""
    df = df.iloc[:, :3]
    df.columns = ["Date", "Time", "Amount_ml"]
    df['Amount_ml'] = pd.to_numeric(df['Amount_ml'], errors='coerce').fillna(0)
    return df

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
def get_holidays():
    client = init_connection()
    ss = client.open("MY ROUTINE 2026")
    try:
        sheet = ss.worksheet("holidays")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="holidays", rows="50", cols="2")
        sheet.append_row(["Date", "Occasion"])
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Occasion"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 2: df[df.shape[1]] = ""
    df = df.iloc[:, :2]
    df.columns = ["Date", "Occasion"]
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
    water_df = get_water_log()
    proj_df = get_project_tasks()
    holidays_df = get_holidays()
    
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    clean_now = now.replace(second=0, microsecond=0).time()
    
    current_day = now.strftime('%A')
    today_str = now.strftime('%Y-%m-%d')
    current_time = now.time()

    running_tasks = log_df[log_df['End_Time'] == 'RUNNING']
    active_count = len(running_tasks)
    
    if active_count > 0:
        st.markdown(f"""
            <div style='position: fixed; bottom: 30px; left: 20px; background-color: #ff4b4b; color: white; padding: 8px 16px; border-radius: 20px; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); font-weight: bold; font-size: 16px; z-index: 9999; pointer-events: none; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 16px; margin-right: 6px; animation: pulse 1.5s infinite;'>⏱️</span> {active_count}
            </div>
        """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["⏱️ Live View", "📅 Schedule", "💧 Hydration", "📊 Projects", "⏳ Timeline", "🔗 Hub"])

    # ==========================================
    # TAB 1: LIVE DASHBOARD
    # ==========================================
    with tab1:
        st.markdown(f"<h3 style='text-align: center; color: #888; margin-top: 0px;'>{current_day} | {now.strftime('%I:%M %p')}</h3>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            flex_on = st.toggle("🔀 Flex", key="flex_toggle")
        with col2:
            holiday_on = st.toggle("🎉 Holiday", key="holiday_toggle")
        with col3:
            if st.button("🔄 Sync", use_container_width=True):
                get_routine_data.clear()
                get_activity_log.clear()
                get_future_tasks.clear()
                get_water_log.clear()
                get_project_tasks.clear()
                get_holidays.clear()
                st.toast("✅ Force Synced with Google Sheets!")
                time.sleep(0.5)
                st.rerun()

        holidays_df['Date_dt'] = pd.to_datetime(holidays_df['Date'], dayfirst=True, errors='coerce')
        
        today_holiday_match = holidays_df[holidays_df['Date_dt'].dt.date == now.date()]
        is_auto_holiday = not today_holiday_match.empty
        auto_occasion = today_holiday_match.iloc[0]['Occasion'] if is_auto_holiday else ""

        effective_day = "Holiday" if (holiday_on or is_auto_holiday) else current_day

        scheduled_activity = "FREE TIME"
        scheduled_activity_start = None
        next_activity = "NONE"
        next_time_str = ""
        scheduled_sub_activities = ""
        scheduled_check_list = ""

        today_schedule = df[df['Day'].str.strip().str.title() == effective_day.title()].to_dict('records')

        for i, row in enumerate(today_schedule):
            try:
                start_str = str(row['Start_Time']).strip()
                end_str = str(row['End_Time']).strip()
                
                start_t = datetime.strptime(start_str, '%H:%M').time()
                if end_str == '0:00': end_t = datetime.strptime('23:59:59', '%H:%M:%S').time()
                else: end_t = datetime.strptime(end_str, '%H:%M').time()

                if start_t <= current_time <= end_t:
                    scheduled_activity = str(row['Activity']).strip().upper()
                    scheduled_activity_start = start_t
                    scheduled_sub_activities = str(row.get('Sub_Activities', '')).strip()
                    scheduled_check_list = str(row.get('check_list', '')).strip()
                    
                    if i + 1 < len(today_schedule):
                        next_row = today_schedule[i+1]
                        next_activity = str(next_row['Activity']).strip().upper()
                        next_time_str = datetime.strptime(str(next_row['Start_Time']).strip(), '%H:%M').strftime('%I:%M %p')
                    else: next_activity = "END OF DAY"
                    break
                    
                elif current_time < start_t and scheduled_activity == "FREE TIME":
                    next_activity = str(row['Activity']).strip().upper()
                    next_time_str = datetime.strptime(start_str, '%H:%M').strftime('%I:%M %p')
                    break
            except ValueError: continue

        if flex_on:
            unique_activities = sorted(list(set([act.strip().upper() for act in df['Activity'] if act.strip()])))
            if "FREE TIME" not in unique_activities: unique_activities.append("FREE TIME")
            
            current_activity = st.selectbox("What are you actually doing right now?", unique_activities, key="flex_sel")
            
            matched_rows = df[df['Activity'].str.strip().str.upper() == current_activity]
            agg_subs = []
            agg_chks = []
            for _, r in matched_rows.iterrows():
                agg_subs.extend([s.strip() for s in str(r.get('Sub_Activities', '')).split(',') if s.strip()])
                agg_chks.extend([c.strip() for c in str(r.get('check_list', '')).split(',') if c.strip()])
            
            current_sub_activities = ",".join(list(dict.fromkeys(agg_subs)))
            current_check_list = ",".join(list(dict.fromkeys(agg_chks)))
            
            current_activity_start = None 
            next_activity = "FLEX MODE ACTIVE"
            next_time_str = "--:--"
        else:
            current_activity = scheduled_activity
            current_activity_start = scheduled_activity_start
            current_sub_activities = scheduled_sub_activities
            current_check_list = scheduled_check_list

        if current_activity in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY", "PEOPLE"]: color = "#ff4b4b" 
        elif current_activity in ["WORK", "REPORT", "TASK"]: color = "#0068c9" 
        elif current_activity == "HEALTH": color = "#2e7b32" 
        elif current_activity in ["SLEEP", "PRE", "TEA", "OUT"]: color = "#ff9f36" 
        else: color = "#333333" 

        st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 10px; margin-bottom: 5px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

        if is_auto_holiday or holiday_on:
            if is_auto_holiday:
                st.markdown(f"<p style='text-align: center; color: #ff9f36; font-weight: bold; font-size: 1.1rem; margin-top: -10px;'>🎉 {auto_occasion} (Holiday Schedule Active)</p>", unsafe_allow_html=True)
            else:
                st.markdown("<p style='text-align: center; color: #ff9f36; font-weight: bold; margin-top: -10px;'>🎉 Running Custom Holiday Schedule</p>", unsafe_allow_html=True)

        if current_activity_start and not flex_on:
            dt_start = datetime.combine(now.date(), current_activity_start)
            dt_start = ist_timezone.localize(dt_start)
            elapsed = now - dt_start
            eh, erem = divmod(int(elapsed.total_seconds()), 3600)
            em = erem // 60
            elapsed_text = f"{eh}h {em}m" if eh > 0 else f"{em}m"
            st.markdown(f"<h3 style='text-align: center; color: #555; margin-top: 0px; margin-bottom: 10px; font-weight: 400;'>⏱️ Elapsed: {elapsed_text}</h3>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

        if next_activity == "FLEX MODE ACTIVE":
            st.markdown(f"<h4 style='text-align: center; color: #e65100; margin-bottom: 20px; font-weight: 400;'>⚠️ Schedule Paused - Logging Custom Activity</h4>", unsafe_allow_html=True)
        elif next_activity not in ["NONE", "END OF DAY"]:
            st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: <b>{next_activity}</b> at {next_time_str}</h4>", unsafe_allow_html=True)
        elif next_activity == "END OF DAY":
            st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: Schedule Complete</h4>", unsafe_allow_html=True)

        # --- SMART HYDRATION TRACKER ---
        st.markdown("---")
        today_water = water_df[water_df['Date'] == today_str]
        total_water_today = today_water['Amount_ml'].sum()
        current_hour_dec = now.hour + now.minute / 60.0
        
        if 4.5 <= current_hour_dec <= 20.5: 
            if not today_water.empty:
                last_water_time_str = today_water.iloc[-1]['Time']
                try:
                    last_water_dt = datetime.strptime(f"{today_str} {last_water_time_str}", "%Y-%m-%d %H:%M")
                    last_water_dt = ist_timezone.localize(last_water_dt)
                    hours_since_water = (now - last_water_dt).total_seconds() / 3600
                    if hours_since_water >= 2.0:
                        st.warning(f"💧 **Hydration Reminder:** It's been {int(hours_since_water)} hours since your last drink. Time for water!")
                except: pass
            else:
                st.warning("💧 **Hydration Reminder:** You haven't logged any water yet today!")
        elif current_hour_dec > 20.5 or current_hour_dec < 4.5:
            st.info("🛑 **Hydration Cut-off Active:** Limit fluid intake to prepare for uninterrupted sleep.")

        st.markdown(f"<h4 style='text-align: center; color: #0288d1; margin-bottom:15px;'>💧 Quick Log Water (Today: {int(total_water_today)}ml)</h4>", unsafe_allow_html=True)
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            if st.button("🥃 250 ml", use_container_width=True):
                wsheet = get_sheet("water_log")
                wsheet.append_row([today_str, now.strftime('%H:%M'), 250])
                get_water_log.clear() 
                st.rerun()
        with col_w2:
            if st.button("🚰 500 ml", use_container_width=True):
                wsheet = get_sheet("water_log")
                wsheet.append_row([today_str, now.strftime('%H:%M'), 500])
                get_water_log.clear() 
                st.rerun()
        with col_w3:
            if st.button("🥛 1000 ml", use_container_width=True):
                wsheet = get_sheet("water_log")
                wsheet.append_row([today_str, now.strftime('%H:%M'), 1000])
                get_water_log.clear() 
                st.rerun()

        # --- SMART SCHEDULE INJECTION & COUNTDOWN ---
        sub_list = [s.strip() for s in current_sub_activities.split(',') if s.strip()]
        chk_list = [c.strip() for c in current_check_list.split(',') if c.strip()]
        all_logged_items = log_df['check_list'].tolist() + log_df['Sub_Activities'].tolist()
        
        upcoming_ui_elements_raw = []

        if not future_df.empty:
            for _, r in future_df.iterrows():
                try:
                    due_dt_str = f"{r['Due_Date']} {r['Due_Time']}"
                    due_dt = ist_timezone.localize(datetime.strptime(due_dt_str, "%Y-%m-%d %H:%M"))
                    time_diff = due_dt - now
                    hours_until_due = time_diff.total_seconds() / 3600
                    
                    formatted_task = f"{r['Task_Name']} [Due: {r['Due_Date'][5:]} {r['Due_Time']}]"
                    
                    status_val = str(r['Status']).strip().upper()
                    is_done_in_sheet = status_val in ['COMPLETED', 'CANCELED']
                    is_done_in_log = any(formatted_task.upper() == str(x).strip().upper() for x in all_logged_items)
                    is_done = is_done_in_sheet or is_done_in_log
                    
                    if is_done: continue
                        
                    if hours_until_due <= 24:
                        sec_diff = time_diff.total_seconds()
                        is_overdue = sec_diff < 0
                        abs_sec = abs(int(sec_diff))
                        h, rem = divmod(abs_sec, 3600)
                        m = rem // 60
                        time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
                        
                        if is_overdue:
                            time_text = f"overdue by {time_str}"
                            text_color = "#ff4b4b" if abs_sec >= 1800 else "#0068c9"
                        else:
                            time_text = f"due in {time_str}"
                            text_color = "#0068c9"
                            
                        html_string = f"&gt; <b style='color: {text_color};'>{r['Task_Name']} ({r['Activity']})</b> {time_text}"
                        upcoming_ui_elements_raw.append((due_dt, r, html_string))
                        
                    if hours_until_due <= 0 and str(r['Activity']).strip().upper() == current_activity:
                        if r['Type'] == 'Sub-Activity': sub_list.append(formatted_task)
                        elif r['Type'] == 'Checklist': chk_list.append(formatted_task)
                except: continue

        if upcoming_ui_elements_raw:
            upcoming_ui_elements_raw.sort(key=lambda x: x[0])
            
            upcoming_count = len(upcoming_ui_elements_raw)
            with st.expander(f"⏳ Upcoming Special Tasks ({upcoming_count})", expanded=False):
                for dt, r, html_text in upcoming_ui_elements_raw:
                    st.markdown(f"<p style='text-align: center; margin-bottom:5px; font-size:16px; color: #d84315;'>{html_text}</p>", unsafe_allow_html=True)
                    with st.expander(f"✏️ Manage Task", expanded=False):
                        tab_resched, tab_cancel = st.tabs(["📅 Reschedule", "❌ Cancel"])
                        with tab_resched:
                            col_d, col_t = st.columns(2)
                            try: curr_date = datetime.strptime(str(r['Due_Date']).strip(), '%Y-%m-%d').date()
                            except: curr_date = now.date()
                            curr_time_str = str(r['Due_Time']).strip()
                            time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
                            if curr_time_str not in time_opts: curr_time_str = "12:00"
                            
                            with col_d: new_date = st.date_input("New Date", value=curr_date, key=f"nd_{r['row_index']}")
                            with col_t: new_time = st.selectbox("New Time", options=time_opts, index=time_opts.index(curr_time_str), key=f"nt_{r['row_index']}")
                                
                            if st.button("Save New Time", key=f"rs_btn_{r['row_index']}", type="primary", use_container_width=True):
                                fsheet = get_sheet("future_tasks")
                                fsheet.update_cell(int(r['row_index']), 1, new_date.strftime('%Y-%m-%d'))
                                fsheet.update_cell(int(r['row_index']), 2, new_time)
                                sheet_log = get_sheet("activity_log")
                                sheet_log.append_row([
                                    today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), 
                                    GS_FORMULA, str(r['Activity']).upper(), "", f"{r['Task_Name']} [RESCHEDULED]", f"Moved to {new_date.strftime('%Y-%m-%d')} {new_time}"
                                ], value_input_option="USER_ENTERED")
                                get_future_tasks.clear() 
                                get_activity_log.clear() 
                                st.success("Task Rescheduled!")
                                time.sleep(1)
                                st.rerun()
                        with tab_cancel:
                            col_r, col_b = st.columns([3, 1])
                            with col_r: cancel_reason = st.text_input("Reason", placeholder="Why are you cancelling?", key=f"rsn_{r['row_index']}", label_visibility="collapsed")
                            with col_b:
                                if st.button("Confirm", key=f"cnf_{r['row_index']}", type="primary"):
                                    if not cancel_reason.strip(): st.error("Enter reason")
                                    else:
                                        fsheet = get_sheet("future_tasks")
                                        fsheet.update_cell(int(r['row_index']), 7, "Canceled")
                                        fsheet.update_cell(int(r['row_index']), 8, cancel_reason)
                                        sheet_log = get_sheet("activity_log")
                                        sheet_log.append_row([
                                            today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), 
                                            GS_FORMULA, str(r['Activity']).upper(), "", f"{r['Task_Name']} [CANCELED]", f"Cancel Reason: {cancel_reason}"
                                        ], value_input_option="USER_ENTERED")
                                        get_future_tasks.clear() 
                                        get_activity_log.clear() 
                                        st.rerun()
                    st.markdown("<hr style='margin-top:5px; margin-bottom:15px;'>", unsafe_allow_html=True)

        # --- UPCOMING HOLIDAYS ---
        future_holidays = holidays_df[holidays_df['Date_dt'].dt.date > now.date()].sort_values('Date_dt')
        
        if not future_holidays.empty:
            upcoming_hols = future_holidays.head(3)
            with st.expander(f"🌴 Upcoming Holidays ({len(upcoming_hols)})", expanded=False):
                for _, h_row in upcoming_hols.iterrows():
                    days_until = (h_row['Date_dt'].date() - now.date()).days
                    day_str = "Tomorrow!" if days_until == 1 else f"in {days_until} days"
                    st.markdown(f"**{h_row['Date_dt'].strftime('%b %d, %Y')}** - {h_row['Occasion']} *( {day_str} )*")

        if chk_list:
            st.markdown("---")
            st.markdown("<h4 style='text-align: center; color: #333;'>✅ Tasks & Reminders</h4>", unsafe_allow_html=True)
            today_logs = log_df[log_df['Date'] == today_str]
            today_logged_tasks = today_logs[today_logs['Activity'] == current_activity]['check_list'].tolist()
            
            for task in chk_list:
                if "[Due:" in task:
                    raw_task = task.split(" [Due:")[0].strip()
                    matches = future_df[(future_df['Task_Name'].str.strip() == raw_task) & (future_df['Type'] == 'Checklist')]
                    if not matches.empty and str(matches.iloc[0]['Status']).strip().upper() in ['COMPLETED', 'CANCELED']: is_done = True
                    else: is_done = any(task.upper() == str(x).strip().upper() for x in all_logged_items)
                else: is_done = any(task.upper() == str(x).strip().upper() for x in today_logged_tasks)
                    
                checked = st.checkbox(task, value=is_done, disabled=is_done, key=f"chk_{task}_{current_activity}")
                if checked and not is_done:
                    sheet_log = get_sheet("activity_log")
                    sheet_log.append_row([
                        today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), 
                        GS_FORMULA, current_activity, "", task, "Checked off"
                    ], value_input_option="USER_ENTERED")
                    get_activity_log.clear() 
                    
                    if "[Due:" in task:
                        raw_task = task.split(" [Due:")[0].strip()
                        matches = future_df[(future_df['Task_Name'].str.strip() == raw_task) & (future_df['Type'] == 'Checklist')]
                        if not matches.empty:
                            r_idx = int(matches.iloc[0]['row_index'])
                            fsheet = get_sheet("future_tasks")
                            fsheet.update_cell(r_idx, 7, "Completed") 
                            get_future_tasks.clear() 
                            
                    st.rerun()

        # ==========================================
        # MULTI-TASKING LOGIC (LIVE TIMERS)
        # ==========================================
        pending_projs = pd.DataFrame()
        if not proj_df.empty:
            pending_projs = proj_df[proj_df['Status'].str.strip().str.title() != 'Completed']
        
        if sub_list or active_count > 0 or not pending_projs.empty:
            st.markdown("---")
            
            st.markdown("<h4 style='text-align: center; color: #333;'>Tap to Track Activity</h4>", unsafe_allow_html=True)
            
            # --- 1. RENDER ALL RUNNING TASKS WITH POMODORO ---
            if active_count > 0:
                for idx, active_row in running_tasks.iterrows():
                    sheet_row = idx + 2 
                    active_main = str(active_row['Activity'])
                    active_sub = str(active_row['Sub_Activities'])
                    display_name = active_sub if active_sub else active_main
                    
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
                    
                    # Trigger double-beep if state transitions (e.g. Focus -> Break)
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
                    
                    is_project = str(active_row['Notes']).strip() == "Project Tracking"
                    new_proj_status = None
                    raw_task_name = ""
                    
                    if is_project:
                        raw_task_name = active_sub.split(" (")[0]
                        curr_stat_matches = proj_df[proj_df['Task Name'] == raw_task_name]['Status']
                        curr_stat = curr_stat_matches.values[0].strip().title() if not curr_stat_matches.empty else "In Progress"
                        
                        status_opts = ["In Progress", "Completed", "Not Started"]
                        try:
                            def_idx = status_opts.index(curr_stat)
                        except ValueError:
                            def_idx = 0
                            
                        new_proj_status = st.selectbox("Update Project Status upon saving:", status_opts, index=def_idx, key=f"pstat_{sheet_row}")

                    col_stop, col_cancel = st.columns(2)
                    with col_stop:
                        if st.button("🛑 SAVE", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                            end_time_log = now.time()

                            log_sheet = get_sheet("activity_log")
                            log_sheet.update_cell(sheet_row, 3, end_time_log.strftime('%H:%M')) 
                            log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                            
                            old_notes = str(active_row['Notes'])
                            if old_notes.strip() == "":
                                log_sheet.update_cell(sheet_row, 8, "Auto-logged via Timer") 
                                
                            if "[Due:" in active_sub:
                                raw_r_task = active_sub.split(" [Due:")[0].strip()
                                matches = future_df[(future_df['Task_Name'].str.strip() == raw_r_task) & (future_df['Type'] == 'Sub-Activity')]
                                if not matches.empty:
                                    r_idx = int(matches.iloc[0]['row_index'])
                                    fsheet = get_sheet("future_tasks")
                                    fsheet.update_cell(r_idx, 7, "Completed") 
                                    get_future_tasks.clear() 
                                    
                            if is_project and new_proj_status:
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
            
            running_subs = running_tasks['Sub_Activities'].tolist()

            # --- 2. RENDER ROUTINE SUB-ACTIVITIES (Not Currently Running) ---
            avail_subs = [t for t in sub_list if t not in running_subs]
            if avail_subs:
                st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #333;'><b>▶️ Routine Tasks:</b></div>", unsafe_allow_html=True)
                cols = st.columns(3)
                for idx, task in enumerate(avail_subs):
                    with cols[idx % 3]:
                        last_done = get_last_done_str(task, log_df, now)
                        last_txt = f"\n(Last: {last_done})" if "[Due:" not in task else ""
                        if st.button(f"▶️ {task}{last_txt}", key=f"btn_{idx}_{task}", use_container_width=True):
                            log_sheet = get_sheet("activity_log")
                            log_sheet.append_row([
                                today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                                current_activity, task, "", "Auto-logged via Timer"
                            ], value_input_option="USER_ENTERED")
                            get_activity_log.clear() 
                            st.rerun()
            
            # --- 3. RENDER PROJECT TRACKER (Not Currently Running) ---
            if not pending_projs.empty:
                avail_projs = pending_projs[~pending_projs['Task Name'].isin([x.split(" (")[0] for x in running_subs])]
                if not avail_projs.empty:
                    st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #0068c9;'><b>🚀 Start a Project Task:</b></div>", unsafe_allow_html=True)
                    
                    col_proj, col_task, col_btn = st.columns([2, 2, 1])
                    
                    with col_proj:
                        unique_projs = sorted(avail_projs['Project Name'].unique().tolist())
                        selected_project = st.selectbox("Project", unique_projs, label_visibility="collapsed", key="live_proj_sel")
                    
                    with col_task:
                        filtered_tasks = avail_projs[avail_projs['Project Name'] == selected_project]['Task Name'].tolist()
                        selected_task = st.selectbox("Task", filtered_tasks, label_visibility="collapsed", key="live_task_sel")

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
                        if st.button("▶️ Start", key="start_proj", use_container_width=True):
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

            # --- 4. RENDER MEETING/VISITOR TRACKER ---
            st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #ff4b4b;'><b>👥 Meeting / Visitor Tracker:</b></div>", unsafe_allow_html=True)
            
            if st.button("⚡ Quick Start (Update Details Later)", use_container_width=True):
                log_sheet = get_sheet("activity_log")
                log_sheet.append_row([
                    today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                    "PEOPLE", "MEETING / VISITOR", "", "Update details later"
                ], value_input_option="USER_ENTERED")
                get_activity_log.clear() 
                st.rerun()

            with st.expander("📝 Or Enter Details Before Starting", expanded=False):
                col_mt1, col_mt2 = st.columns(2)
                with col_mt1: 
                    interaction_type = st.selectbox("Interaction Type", ["Attend Visitor", "Meet People"], key="live_mtg_type")
                
                people_logs = log_df[log_df['Activity'] == 'PEOPLE']['Sub_Activities'].dropna().astype(str)
                extracted_names = []
                for val in people_logs:
                    if " - " in val: extracted_names.append(val.split(" - ", 1)[-1].strip())
                    else: extracted_names.append(val.strip())
                unique_old_people = sorted(list(set([n for n in extracted_names if n])))
                
                with col_mt2: 
                    person_type = st.selectbox("Person", ["-- New Person --"] + unique_old_people, key="live_mtg_person")
                
                if person_type == "-- New Person --":
                    person_name = st.text_input("Name of New Person", key="live_mtg_new_name")
                else:
                    person_name = person_type

                topic_talk = st.text_input("Topic of Talking", key="live_mtg_topic")
                purpose_visit = st.text_input("Purpose of Visit", key="live_mtg_purpose")
                
                if st.button("▶️ Start with Details", type="primary", use_container_width=True):
                    final_name = person_name.strip() if person_name else "Unknown"
                    sub_act_str = f"{interaction_type} - {final_name}"
                    notes_str = f"Topic: {topic_talk} | Purpose: {purpose_visit}"
                    
                    log_sheet = get_sheet("activity_log")
                    log_sheet.append_row([
                        today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                        "PEOPLE", sub_act_str.upper(), "", notes_str
                    ], value_input_option="USER_ENTERED")
                    get_activity_log.clear() 
                    st.rerun()

        st.markdown("---")
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
        
        with st.expander("🗓️ Schedule Future Task"):
            with st.form("schedule_future_form", clear_on_submit=True):
                st.markdown("### Attach Task to a Future Activity")
                unique_activities = [act for act in df['Activity'].unique() if act.strip()]
                f_act = st.selectbox("Parent Category", unique_activities, key="f_act")
                f_type = st.radio("Task Type", ["Checklist", "Sub-Activity"], horizontal=True, key="f_type")
                f_entity = st.selectbox("Entity", ["Personal", "School", "People"], key="f_entity")
                f_name = st.text_input("Task Details", placeholder="e.g., Pay Electricity Bill", key="f_name")
                time_options = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
                now_str = clean_now.strftime('%H:%M')
                
                col1, col2 = st.columns(2)
                with col1: f_date = st.date_input("Due Date", value=now.date(), key="f_date")
                with col2: 
                    f_time_str = st.selectbox("Due Time (Type to search)", options=time_options, index=time_options.index(now_str), key="f_time")
                    f_time = datetime.strptime(f_time_str, '%H:%M').time()
                    
                if st.form_submit_button("Schedule Task", use_container_width=True):
                    if f_name:
                        fsheet = get_sheet("future_tasks")
                        fsheet.append_row([
                            f_date.strftime('%Y-%m-%d'),
                            f_time.strftime('%H:%M'),
                            f_act.upper().strip(),
                            f_type,
                            f_name.strip(),
                            f_entity,
                            "Pending",
                            ""
                        ])
                        get_future_tasks.clear() 
                        st.success("Task Scheduled! It will appear 24 hours before due time.")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.error("Please enter task details.")

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
                        sheet_log = get_sheet("activity_log")
                        sheet_log.append_row([
                            log_date.strftime('%Y-%m-%d'), log_start.strftime('%H:%M'), log_end.strftime('%H:%M'), 
                            GS_FORMULA, log_activity.upper().strip(), log_sub_activity.upper().strip(),
                            log_chk.strip(), log_notes
                        ], value_input_option="USER_ENTERED")
                        get_activity_log.clear() 
                        st.success("Activity logged!")
                        time.sleep(1)
                        st.rerun()
                    else: st.error("Please enter a Main Category.")

    # ==========================================
    # TAB 2: SCHEDULE EDITOR
    # ==========================================
    with tab2:
        st.markdown("<h3 style='text-align: center; color: #555; margin-bottom: 5px;'>📅 Smart Schedule Manager</h3>", unsafe_allow_html=True)

        days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Holiday"]
        
        # --- ADVANCED BATCH TOOLS & FREE TIME FINDER ---
        with st.expander("🛠️ Advanced Tools: Batch Add, Replace & Free Time", expanded=False):
            tool_mode = st.radio("Select Tool:", ["🔍 Find Free Time", "➕ Batch Add Task", "🔄 Find & Replace"], horizontal=True)
            
            if tool_mode == "🔍 Find Free Time":
                st.markdown("#### Find Gaps in Your Routine")
                free_day = st.selectbox("Select Day to Analyze", days_of_week, key="free_day")
                day_df_free = df[df['Day'].str.strip().str.title() == free_day.title()].copy()
                
                if not day_df_free.empty:
                    time_blocks = []
                    for _, r in day_df_free.iterrows():
                        try:
                            st_m = int(r['Start_Time'].split(':')[0])*60 + int(r['Start_Time'].split(':')[1])
                            et_str = r['End_Time']
                            if et_str.strip() in ['0:00', '00:00']: et_m = 24 * 60
                            else: et_m = int(et_str.split(':')[0])*60 + int(et_str.split(':')[1])
                            time_blocks.append((st_m, et_m, r['Activity']))
                        except: pass
                    
                    time_blocks.sort(key=lambda x: x[0])
                    
                    free_slots = []
                    current_min = 0
                    for block in time_blocks:
                        if block[0] > current_min: free_slots.append((current_min, block[0]))
                        current_min = max(current_min, block[1])
                    
                    if current_min < 24 * 60: free_slots.append((current_min, 24 * 60))
                        
                    if free_slots:
                        st.success(f"Found {len(free_slots)} free time slots on {free_day}:")
                        for start, end in free_slots:
                            s_str = datetime.strptime(f"{start//60:02d}:{start%60:02d}", '%H:%M').strftime('%I:%M %p')
                            e_str = "12:00 AM" if end == 24*60 else datetime.strptime(f"{end//60:02d}:{end%60:02d}", '%H:%M').strftime('%I:%M %p')
                            st.markdown(f"- **{s_str} to {e_str}** ({end - start} mins available)")
                    else: st.info("This day is completely fully scheduled!")
                else: st.info("No routine set for this day. The whole day is free!")

            elif tool_mode == "➕ Batch Add Task":
                st.markdown("#### Add Task to Multiple Days")
                b_days = st.multiselect("Select Days", days_of_week, default=[current_day], key="b_days")
                
                col1, col2 = st.columns(2)
                with col1: b_start = st.time_input("Start Time", value=datetime.strptime('09:00', '%H:%M').time(), key="b_start")
                with col2: b_end = st.time_input("End Time", value=datetime.strptime('10:00', '%H:%M').time(), key="b_end")
                
                b_act = st.text_input("Activity Name (e.g. PYTHON CODING)").upper()
                b_sub = st.text_input("Sub-Activities (comma separated)")
                b_chk = st.text_input("Checklist (comma separated)")
                b_overwrite = st.checkbox("⚠️ Overwrite existing tasks in this time slot?", value=False)
                
                if st.button("Apply to Selected Days", type="primary"):
                    if not b_days or not b_act: st.error("Please provide both Days and an Activity Name.")
                    else:
                        ns_min = b_start.hour * 60 + b_start.minute
                        ne_min = b_end.hour * 60 + b_end.minute
                        if ne_min == 0: ne_min = 24 * 60
                        
                        if ne_min <= ns_min: st.error("End time must be after start time.")
                        else:
                            full_df = df.copy()
                            rows_to_keep = []
                            for _, r in full_df.iterrows():
                                d_title = str(r['Day']).strip().title()
                                if d_title in [d.title() for d in b_days] and b_overwrite:
                                    try:
                                        rs_min = int(r['Start_Time'].split(':')[0])*60 + int(r['Start_Time'].split(':')[1])
                                        et_str = r['End_Time']
                                        re_min = 24*60 if et_str.strip() in ['0:00', '00:00'] else int(et_str.split(':')[0])*60 + int(et_str.split(':')[1])
                                        if max(ns_min, rs_min) < min(ne_min, re_min): continue 
                                    except: pass
                                rows_to_keep.append(r)
                            
                            filtered_df = pd.DataFrame(rows_to_keep, columns=full_df.columns)
                            dur_str = f"{(ne_min - ns_min)//60}:{(ne_min - ns_min)%60:02d}"
                            start_s = b_start.strftime('%H:%M')
                            end_s = b_end.strftime('%H:%M')
                            
                            new_rows = [{"Day": d, "Start_Time": start_s, "End_Time": end_s, "Duration": dur_str, "Activity": b_act, "Sub_Activities": b_sub, "check_list": b_chk} for d in b_days]
                            final_df = pd.concat([filtered_df, pd.DataFrame(new_rows)], ignore_index=True)
                            
                            day_map = {d: i for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Holiday"])}
                            final_df['Day_Idx'] = final_df['Day'].str.title().map(day_map)
                            def get_st_min(t_str):
                                try: return int(t_str.split(':')[0])*60 + int(t_str.split(':')[1])
                                except: return 0
                            final_df['ST_Min'] = final_df['Start_Time'].apply(get_st_min)
                            final_df = final_df.sort_values(['Day_Idx', 'ST_Min']).drop(columns=['Day_Idx', 'ST_Min'])
                            
                            routine_sheet = get_sheet("routine_master")
                            routine_sheet.clear()
                            routine_sheet.update(values=[final_df.columns.values.tolist()] + final_df.values.tolist(), range_name="A1")
                            
                            get_routine_data.clear()
                            st.success(f"Added '{b_act}' to {len(b_days)} days!")
                            time.sleep(1)
                            st.rerun()

            elif tool_mode == "🔄 Find & Replace":
                st.markdown("#### Replace Items Across Schedule")
                r_days = st.multiselect("Select Days to Search", days_of_week, default=days_of_week, key="r_days")
                
                target_col = st.radio("What do you want to replace?", ["Activity", "Sub-Activity", "Checklist"], horizontal=True)
                
                if target_col == "Activity":
                    unique_vals = sorted(list(set([a.strip().upper() for a in df['Activity'] if a.strip()])))
                elif target_col == "Sub-Activity":
                    all_items = []
                    for val in df['Sub_Activities']:
                        all_items.extend([s.strip() for s in str(val).split(',') if s.strip()])
                    unique_vals = sorted(list(set(all_items)))
                else: 
                    all_items = []
                    for val in df['check_list']:
                        all_items.extend([c.strip() for c in str(val).split(',') if c.strip()])
                    unique_vals = sorted(list(set(all_items)))
                
                old_val = st.selectbox("Target Item to Replace", unique_vals) if unique_vals else None
                new_val = st.text_input("New Item Name")
                
                if st.button("Replace Item", type="primary"):
                    if not r_days or not new_val or not old_val: 
                        st.error("Please fill all fields.")
                    else:
                        full_df = df.copy()
                        count = 0
                        for idx, r in full_df.iterrows():
                            if str(r['Day']).strip().title() in [d.title() for d in r_days]:
                                if target_col == "Activity":
                                    if str(r['Activity']).strip().upper() == old_val.upper():
                                        full_df.at[idx, 'Activity'] = new_val.upper()
                                        count += 1
                                elif target_col == "Sub-Activity":
                                    items = [s.strip() for s in str(r['Sub_Activities']).split(',') if s.strip()]
                                    if old_val in items:
                                        items = [new_val if x == old_val else x for x in items]
                                        full_df.at[idx, 'Sub_Activities'] = ", ".join(items)
                                        count += 1
                                elif target_col == "Checklist":
                                    items = [c.strip() for c in str(r['check_list']).split(',') if c.strip()]
                                    if old_val in items:
                                        items = [new_val if x == old_val else x for x in items]
                                        full_df.at[idx, 'check_list'] = ", ".join(items)
                                        count += 1
                        
                        if count > 0:
                            routine_sheet = get_sheet("routine_master")
                            routine_sheet.clear()
                            routine_sheet.update(values=[full_df.columns.values.tolist()] + full_df.values.tolist(), range_name="A1")
                            
                            get_routine_data.clear()
                            st.success(f"Replaced {count} instances of '{old_val}' with '{new_val}'!")
                            time.sleep(1)
                            st.rerun()
                        else: st.info(f"No instances of '{old_val}' found on selected days.")

        st.markdown("---")
        
        target_day = st.selectbox("Select Day to Edit Manually", days_of_week, index=days_of_week.index(effective_day))
        
        st.markdown(f"<h3 style='text-align: center; color: #555; margin-bottom: 5px;'>{target_day}'s Full Routine</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888; font-size: 14px; margin-bottom: 20px;'>Tap any cell to edit. Scroll right to see Sub-Activities and Checklists.</p>", unsafe_allow_html=True)
        
        target_full_df = df[df['Day'].str.strip().str.title() == target_day.title()].copy()
        
        if not target_full_df.empty:
            edit_df = target_full_df[['Start_Time', 'End_Time', 'Activity', 'Sub_Activities', 'check_list']].copy()
            
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
                hide_index=True, use_container_width=True, num_rows="dynamic", key="schedule_editor"
            )
            
            if st.button(f"💾 Save Changes for {target_day}", use_container_width=True):
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
                        
                        if end_str in ['00:00', '0:00'] or e_dt < s_dt: e_dt = e_dt.replace(day=e_dt.day + 1)
                        duration_td = e_dt - s_dt
                        h, m = divmod(duration_td.seconds, 3600)
                        duration_str = f"{h}:{m//60:02d}"
                        
                        sub_act = str(row.get('Sub_Activities', '')).strip()
                        if sub_act == 'nan': sub_act = ""
                        chk_act = str(row.get('check_list', '')).strip()
                        if chk_act == 'nan': chk_act = ""
                        
                        new_rows.append([target_day, start_str, end_str, duration_str, str(row['Activity']).strip().upper(), sub_act, chk_act])

                    full_df = df.copy()
                    other_days_df = full_df[full_df['Day'].str.strip().str.title() != target_day.title()]
                    new_target_df = pd.DataFrame(new_rows, columns=["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list"])
                    final_df = pd.concat([other_days_df, new_target_df], ignore_index=True)
                    
                    routine_sheet = get_sheet("routine_master")
                    routine_sheet.clear() 
                    data_to_upload = [final_df.columns.values.tolist()] + final_df.values.tolist()
                    routine_sheet.update(values=data_to_upload, range_name="A1")
                    
                    get_routine_data.clear() 
                    st.success("Schedule successfully updated!")
                    time.sleep(1)
                    st.rerun()

            st.markdown("---")
            st.markdown("<h4 style='text-align: center; color: #555; margin-bottom: 20px;'>📈 Scheduled Summary</h4>", unsafe_allow_html=True)
            target_full_df['Total_Minutes'] = target_full_df['Duration'].apply(parse_duration_to_minutes)
            schedule_summary = target_full_df.groupby('Activity')['Total_Minutes'].sum().sort_values(ascending=False)
            cols_sched = st.columns(min(len(schedule_summary), 3))
            col_idx_sched = 0
            for act, total_mins in schedule_summary.items():
                hours, remainder_mins = divmod(total_mins, 60)
                display_time = f"{int(hours)}:{int(remainder_mins):02d}"
                with cols_sched[col_idx_sched % 3]:
                    st.metric(label=act, value=display_time)
                col_idx_sched += 1
        else: st.info(f"No routine scheduled for {target_day}. You can add one above!")

    # ==========================================
    # TAB 3: HYDRATION
    # ==========================================
    with tab3:
        st.markdown("<h3 style='text-align: center; color: #0288d1;'>💧 Hydration Tracker</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Daily Target: 3500 ml</p>", unsafe_allow_html=True)
        
        water_df['Date_dt'] = pd.to_datetime(water_df['Date'], errors='coerce')
        today_dt = pd.to_datetime(today_str)
        
        t_day, t_week, t_month = st.tabs(["Today", "Past 7 Days", "This Month"])
        
        with t_day:
            today_sum = water_df[water_df['Date'] == today_str]['Amount_ml'].sum()
            progress = min(today_sum / 3500.0, 1.0)
            
            st.markdown(f"<h2 style='text-align: center; color: #0288d1;'>{int(today_sum)} ml</h2>", unsafe_allow_html=True)
            st.progress(progress)
            if progress >= 1.0: st.success("Daily target reached!")
            
            today_logs = water_df[water_df['Date'] == today_str].copy()
            if not today_logs.empty:
                st.dataframe(today_logs[['Time', 'Amount_ml']].sort_values('Time', ascending=False), use_container_width=True, hide_index=True)
                
        with t_week:
            last_7 = water_df[water_df['Date_dt'] >= (today_dt - timedelta(days=6))].copy()
            if not last_7.empty:
                daily_grouped = last_7.groupby(last_7['Date_dt'].dt.strftime('%a, %b %d'))['Amount_ml'].sum()
                st.bar_chart(daily_grouped, color="#29b6f6")
            else: st.info("No data for the past 7 days.")
                
        with t_month:
            this_month = water_df[water_df['Date_dt'].dt.month == today_dt.month].copy()
            if not this_month.empty:
                daily_grouped_m = this_month.groupby(this_month['Date_dt'].dt.day)['Amount_ml'].sum()
                st.line_chart(daily_grouped_m, color="#0288d1")
            else: st.info("No data for this month.")

    # ==========================================
    # TAB 4: PROJECTS
    # ==========================================
    with tab4:
        st.markdown("<h3 style='text-align: center; color: #0068c9;'>📊 Project Tracking</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        status_colors = {"Completed": "#2e7b32", "In Progress": "#0068c9", "Not Started": "#ff9f36"}
        
        if not proj_df.empty:
            plot_df = proj_df.copy()
            plot_df['Start Date'] = pd.to_datetime(plot_df['Start Date'], errors='coerce')
            plot_df['End Date'] = pd.to_datetime(plot_df['End Date'], errors='coerce')
            plot_df = plot_df.dropna(subset=['Start Date', 'End Date'])
            
            if not plot_df.empty:
                st.markdown("### 📈 Overall Progress")
                project_stats = plot_df.groupby('Project Name').apply(
                    lambda x: (x['Status'].str.strip().str.title() == 'Completed').sum() / len(x)
                ).reset_index(name='Progress')
                
                cols = st.columns(3)
                for i, row in project_stats.iterrows():
                    with cols[i % 3]:
                        percent_complete = int(row['Progress'] * 100)
                        st.markdown(f"""
                        <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 5px; height: 110px;'>
                            <p style='margin: 0; font-size: 16px; font-weight: 600; color: #333; line-height: 1.2; word-wrap: break-word;'>{row['Project Name']}</p>
                            <h2 style='margin: 0; color: #0068c9; padding-top: 5px;'>{percent_complete}%</h2>
                        </div>
                        """, unsafe_allow_html=True)
                        st.progress(row['Progress'])
                        st.markdown("<br>", unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                col_gantt, col_pie = st.columns([2, 1])
                with col_gantt:
                    st.markdown("#### 🗓️ Task Timeline")
                    plot_df['Status'] = plot_df['Status'].str.strip().str.title()
                    plot_df = plot_df.sort_values('Start Date')
                    fig_gantt = px.timeline(plot_df, x_start="Start Date", x_end="End Date", y="Task Name", color="Status", color_discrete_map=status_colors, hover_data=["Project Name"])
                    fig_gantt.update_yaxes(autorange="reversed", tickmode='linear')
                    fig_gantt.update_layout(margin=dict(l=0, r=0, t=30, b=0), xaxis_title="", yaxis_title="", showlegend=False)
                    st.plotly_chart(fig_gantt, use_container_width=True)
                    
                with col_pie:
                    st.markdown("#### 📌 Status")
                    status_counts = plot_df['Status'].value_counts().reset_index()
                    status_counts.columns = ['Status', 'Count']
                    fig_pie = px.pie(status_counts, names='Status', values='Count', color='Status', color_discrete_map=status_colors, hole=0.45)
                    fig_pie.update_layout(margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Project dates are missing or invalid. Please update them.")
        else:
            st.info("No project tasks found. Add your first task below!")
            
        st.markdown("---")    
        with st.expander("➕ Add New Project Task"):
            with st.form("add_project_task"):
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
                
                if st.form_submit_button("Add Task", use_container_width=True):
                    final_p_name = p_name_new.strip() if p_name_new.strip() else (p_name_sel if p_name_sel != "-- Select Existing Project --" else "")
                    
                    if p_task and final_p_name:
                        psheet = get_sheet("project_tasks")
                        psheet.append_row([p_task.strip(), final_p_name, p_status, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                        get_project_tasks.clear() 
                        st.success("Task added!")
                        time.sleep(1)
                        st.rerun()
                    else: st.error("Task Name and Project Name are required.")

    # ==========================================
    # TAB 5: TIMELINE (DAILY AUDIT)
    # ==========================================
    with tab5:
        st.markdown("<h3 style='text-align: center; color: #555;'>⏳ Daily Activity Timeline</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Audit your day to find unlogged time and gaps.</p>", unsafe_allow_html=True)
        
        selected_timeline_date = st.date_input("Select Date to Review", value=now.date(), key="timeline_date_sel")
        selected_date_str = selected_timeline_date.strftime('%Y-%m-%d')
        
        day_logs = log_df[(log_df['Date'] == selected_date_str) & (log_df['End_Time'] != 'RUNNING')].copy()
        
        if not day_logs.empty:
            day_logs['Start_DT'] = pd.to_datetime(day_logs['Date'] + ' ' + day_logs['Start_Time'], errors='coerce')
            day_logs['End_DT'] = pd.to_datetime(day_logs['Date'] + ' ' + day_logs['End_Time'], errors='coerce')
            
            mask = day_logs['End_DT'] < day_logs['Start_DT']
            day_logs.loc[mask, 'End_DT'] = day_logs.loc[mask, 'End_DT'] + pd.Timedelta(days=1)
            
            day_logs = day_logs.sort_values('Start_DT').dropna(subset=['Start_DT', 'End_DT'])
            
            timeline_events = []
            last_end_time = None
            
            for _, row in day_logs.iterrows():
                current_start = row['Start_DT']
                current_end = row['End_DT']
                
                if last_end_time and current_start > last_end_time:
                    gap_duration = (current_start - last_end_time).total_seconds() / 60
                    if gap_duration > 0:
                        if gap_duration <= 5: 
                            timeline_events.append({
                                'type': 'transition',
                                'start': last_end_time.strftime('%I:%M %p'),
                                'end': current_start.strftime('%I:%M %p'),
                                'duration': int(gap_duration),
                                'activity': 'Transition',
                                'sub': '',
                                'notes': ''
                            })
                        else: 
                            timeline_events.append({
                                'type': 'gap',
                                'start': last_end_time.strftime('%I:%M %p'),
                                'end': current_start.strftime('%I:%M %p'),
                                'duration': int(gap_duration),
                                'activity': 'Unlogged Time / Break',
                                'sub': '',
                                'notes': ''
                            })
                
                dur_mins = (current_end - current_start).total_seconds() / 60
                timeline_events.append({
                    'type': 'task',
                    'start': current_start.strftime('%I:%M %p'),
                    'end': current_end.strftime('%I:%M %p'),
                    'duration': int(dur_mins),
                    'activity': str(row['Activity']).upper(),
                    'sub': str(row['Sub_Activities']).title(),
                    'notes': str(row['Notes'])
                })
                
                if last_end_time is None or current_end > last_end_time:
                    last_end_time = current_end
            
            for event in timeline_events:
                eh, em = divmod(event['duration'], 60)
                if eh > 0 and em > 0:
                    dur_display = f"{eh}h {em}m"
                elif eh > 0:
                    dur_display = f"{eh}h"
                else:
                    dur_display = f"{em}m"

                if event['type'] == 'transition':
                    st.markdown(f"""
                    <div style='background-color: #fff3e0; border: 1px solid #ffb74d; padding: 8px; border-radius: 6px; margin-bottom: 10px; text-align: center; color: #e65100; font-size: 14px;'>
                        <b>{event['start']} - {event['end']}</b> | ⏳ Transition Time: {dur_display}
                    </div>
                    """, unsafe_allow_html=True)
                    
                elif event['type'] == 'gap':
                    col_g1, col_g2 = st.columns([3, 1])
                    with col_g1:
                        st.markdown(f"""
                        <div style='background-color: #fafafa; border: 2px dashed #cccccc; padding: 10px; border-radius: 8px; margin-bottom: 10px; text-align: center; color: #888;'>
                            <b>{event['start']} - {event['end']}</b> (Gap: {dur_display})<br>
                            <em>{event['activity']}</em>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_g2:
                        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                        if st.button("☕ Log as Break", key=f"gap_{event['start']}_{event['end']}", use_container_width=True):
                            start_24 = datetime.strptime(event['start'], '%I:%M %p').strftime('%H:%M')
                            end_24 = datetime.strptime(event['end'], '%I:%M %p').strftime('%H:%M')
                            
                            sheet_log = get_sheet("activity_log")
                            sheet_log.append_row([
                                selected_date_str, start_24, end_24, 
                                GS_FORMULA, "FREE TIME", "Planned Break",
                                "", "Logged from Timeline Gap"
                            ], value_input_option="USER_ENTERED")
                            get_activity_log.clear() 
                            st.rerun()
                else:
                    cat = event['activity']
                    if cat in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY", "PEOPLE"]: border_color = "#ff4b4b" 
                    elif cat in ["WORK", "REPORT", "TASK"]: border_color = "#0068c9" 
                    elif cat == "HEALTH": border_color = "#2e7b32" 
                    elif cat in ["SLEEP", "PRE", "TEA", "OUT"]: border_color = "#ff9f36" 
                    elif cat == "FREE TIME": border_color = "#29b6f6" 
                    else: border_color = "#555555"
                    
                    sub_text = f"<br><b>{event['sub']}</b>" if event['sub'] else ""
                    note_text = f"<br><span style='font-size: 13px; color: #666;'>{event['notes']}</span>" if event['notes'] else ""
                    
                    st.markdown(f"""
                    <div style='background-color: white; border-left: 6px solid {border_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 10px 15px; border-radius: 4px; margin-bottom: 10px;'>
                        <div style='color: #888; font-size: 14px;'>{event['start']} - {event['end']} ({dur_display})</div>
                        <div style='color: {border_color}; font-weight: bold; font-size: 16px;'>{event['activity']}</div>
                        <div style='color: #333;'>{sub_text}{note_text}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
            # --- DAILY SUMMARY ---
            st.markdown("---")
            st.markdown("<h4 style='text-align: center; color: #555;'>📊 Daily Summary</h4>", unsafe_allow_html=True)
            
            total_tracked = sum(e['duration'] for e in timeline_events if e['type'] == 'task')
            total_gap = sum(e['duration'] for e in timeline_events if e['type'] == 'gap')
            
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                th, tm = divmod(total_tracked, 60)
                st.metric(label="Total Tracked Time", value=f"{int(th)}h {int(tm)}m")
            with col_s2:
                gh, gm = divmod(total_gap, 60)
                st.metric(label="Total Unlogged Time", value=f"{int(gh)}h {int(gm)}m")
            with col_s3:
                efficiency = (total_tracked / (total_tracked + total_gap)) * 100 if (total_tracked + total_gap) > 0 else 0
                st.metric(label="Tracking Efficiency", value=f"{int(efficiency)}%")
                
            category_totals = {}
            for e in timeline_events:
                if e['type'] == 'task':
                    cat = e['activity']
                    category_totals[cat] = category_totals.get(cat, 0) + e['duration']
                    
            if category_totals:
                st.markdown("<h5 style='color: #555; margin-top: 15px;'>Time by Category</h5>", unsafe_allow_html=True)
                cat_df = pd.DataFrame(list(category_totals.items()), columns=['Category', 'Minutes'])
                cat_df = cat_df.sort_values(by='Minutes', ascending=False)
                
                cat_cols = st.columns(min(len(cat_df), 4))
                for idx, row in cat_df.iterrows():
                    ch, cm = divmod(row['Minutes'], 60)
                    col_idx = idx % 4 if len(cat_df) >= 4 else idx
                    with cat_cols[col_idx]:
                        st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:8px; text-align:center; margin-bottom:10px;'><b style='color:#333;'>{row['Category']}</b><br><span style='color:#0068c9;'>{int(ch)}h {int(cm)}m</span></div>", unsafe_allow_html=True)
                        
        else:
            st.info(f"No completed activities logged for {selected_date_str}.")

    # ==========================================
    # TAB 6: APP HUB
    # ==========================================
    with tab6:
        st.markdown("<h3 style='text-align: center; color: #555; margin-bottom: 20px;'>🔗 Quick Links</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888; margin-bottom: 30px;'>Access your other modules directly from here.</p>", unsafe_allow_html=True)
        
        st.link_button("🏫 Admission Hub", "https://your-admission-hub-url.streamlit.app", use_container_width=True)
        st.link_button("📱 Main Dashboard (app.py)", "https://your-main-app-url.streamlit.app", use_container_width=True)
        st.link_button("📋 Form Manager", "https://your-form-manager-url.streamlit.app", use_container_width=True)
        st.link_button("🪪 ID Card Generator", "https://your-id-card-url.streamlit.app", use_container_width=True)

except Exception as e:
    st.error(f"System Error: {e}")
