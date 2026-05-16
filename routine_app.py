import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
from streamlit_autorefresh import st_autorefresh

GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

st.set_page_config(page_title="Live Routine Hub", page_icon="⏱️", layout="centered")

if 'active_main_task' not in st.session_state:
    st.session_state.active_main_task = None
    st.session_state.active_sub_task = None
    st.session_state.active_start_time = None

if 'pomodoro_state' not in st.session_state:
    st.session_state.pomodoro_state = {}

st_autorefresh(interval=120000, key="routine_refresh")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
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
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.9; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.9; }
    }
    details > summary {
        list-style: none;
    }
    details > summary::-webkit-details-marker {
        display: none;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Database Connection & Caching
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def get_main_spreadsheet(): return init_connection().open("MY ROUTINE 2026")
def get_money_spreadsheet(): return init_connection().open("sk_money_location")
def get_sheet(tab_name): return get_main_spreadsheet().worksheet(tab_name)

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try: sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
    except TypeError: sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=600)
def get_tracker_data():
    try:
        sheet = init_connection().open("Personal_Dashboard_Data").worksheet("Tracker")
        records = sheet.get_all_records()
        return {row['App Name']: str(row['Last Opened']) for row in records}
    except Exception: return {}

@st.cache_data(ttl=300) 
def get_routine_data():
    data = get_sheet("routine_master").get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 7: df[df.shape[1]] = ""
    df = df.iloc[:, :7]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list"]
    df = df[df["Day"].astype(str).str.strip() != ""]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

@st.cache_data(ttl=300)
def get_app_control_data():
    try:
        sheet = get_sheet("app_control")
        data = sheet.get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=["Time_Slot_Start", "Time_Slot_End", "Duration", "App"])
        df = pd.DataFrame(data[1:], columns=data[0])
        while df.shape[1] < 4: df[df.shape[1]] = ""
        df = df.iloc[:, :4]
        df.columns = ["Time_Slot_Start", "Time_Slot_End", "Duration", "App"]
        return df
    except Exception:
        return pd.DataFrame(columns=["Time_Slot_Start", "Time_Slot_End", "Duration", "App"])

@st.cache_data(ttl=300)
def get_activity_log():
    data = get_sheet("activity_log").get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

@st.cache_data(ttl=300)
def get_future_tasks():
    ss = get_main_spreadsheet()
    try: sheet = ss.worksheet("future_tasks")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="future_tasks", rows="100", cols="8")
        smart_append_row(sheet, ["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "Cancel_Reason"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "Cancel_Reason", "row_index"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "Cancel_Reason"]
    df = df[df["Due_Date"].astype(str).str.strip() != ""] 
    df['row_index'] = df.index + 2 
    return df

@st.cache_data(ttl=300)
def get_holidays():
    ss = get_main_spreadsheet()
    try: sheet = ss.worksheet("holidays")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="holidays", rows="50", cols="2")
        smart_append_row(sheet, ["Date", "Occasion"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Date", "Occasion"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 2: df[df.shape[1]] = ""
    df = df.iloc[:, :2]
    df.columns = ["Date", "Occasion"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    return df

@st.cache_data(ttl=300)
def get_payment_checklist():
    try: sheet = get_money_spreadsheet().worksheet("PAYMENT_CHECKLIST")
    except Exception: return pd.DataFrame(columns=["Month", "Bill_Name", "Type", "Est_Amount", "Due_Date", "Status", "Fund", "Account", "Actual_Paid", "row_index"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Month", "Bill_Name", "Type", "Est_Amount", "Due_Date", "Status", "Fund", "Account", "Actual_Paid", "row_index"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 9: df[df.shape[1]] = ""
    df = df.iloc[:, :9]
    df.columns = ["Month", "Bill_Name", "Type", "Est_Amount", "Due_Date", "Status", "Fund", "Account", "Actual_Paid"]
    df = df[df["Month"].astype(str).str.strip() != ""] 
    df['row_index'] = df.index + 2
    return df

@st.cache_data(ttl=300)
def get_must_do_tasks():
    ss = get_main_spreadsheet()
    try: sheet = ss.worksheet("must_do")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="must_do", rows="100", cols="2")
        smart_append_row(sheet, ["Main Category", "Task Name"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Main Category", "Task Name"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 2: df[df.shape[1]] = ""
    df = df.iloc[:, :2]
    df.columns = ["Main Category", "Task Name"]
    df = df[df["Main Category"].astype(str).str.strip() != ""] 
    return df

@st.cache_data(ttl=300)
def get_pre_tasks():
    ss = get_main_spreadsheet()
    try: sheet = ss.worksheet("PRE")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="PRE", rows="100", cols="2")
        smart_append_row(sheet, ["Main Category", "Task Name"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Main Category", "Task Name"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 2: df[df.shape[1]] = ""
    df = df.iloc[:, :2]
    df.columns = ["Main Category", "Task Name"]
    df = df[df["Main Category"].astype(str).str.strip() != ""] 
    return df

def parse_duration_to_minutes(dur_str):
    try:
        h, m = map(int, str(dur_str).strip().split(':'))
        return (h * 60) + m
    except: return 0

def get_last_done_str(item_name, log_df, now, col_name='Sub_Activities'):
    completed_logs = log_df[log_df['End_Time'] != 'RUNNING']
    matches = completed_logs[completed_logs[col_name].astype(str).str.strip().str.upper() == item_name.upper()]
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

def get_app_time_str(app_name, tracker_data, now_dt):
    val = tracker_data.get(app_name, "")
    if not val: return "Never"
    try:
        dt_naive = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        dt_aware = now_dt.tzinfo.localize(dt_naive)
        diff = now_dt - dt_aware
        if diff.days > 0: return f"{diff.days}d ago"
        elif diff.seconds >= 3600: return f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60: return f"{diff.seconds // 60}m ago"
        else: return "Just now"
    except: return "N/A"

def log_and_open_app(app_name, target_file, cached_data, now_dt):
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    try:
        sheet = init_connection().open("Personal_Dashboard_Data").worksheet("Tracker") 
        cell = sheet.find(app_name)
        if cell: sheet.update_cell(cell.row, 2, now_str)
        else: sheet.append_row([app_name, now_str])
    except Exception as e: print(f"Silent log failure: {e}")
        
    cached_data[app_name] = now_str 
    st.switch_page(target_file)

# ==========================================
# Main Logic
# ==========================================
try:
    df = get_routine_data()
    app_control_df = get_app_control_data()
    log_df = get_activity_log() 
    future_df = get_future_tasks()
    holidays_df = get_holidays()
    payment_df = get_payment_checklist()
    must_do_df = get_must_do_tasks()
    pre_df = get_pre_tasks()
    tracker_data = get_tracker_data()
    
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    clean_now = now.replace(second=0, microsecond=0).time()
    
    current_day = now.strftime('%A')
    today_str = now.strftime('%Y-%m-%d')
    current_time = now.time()

    # --- HARDCODED STATE TO BYPASS REMOVED BUTTONS ---
    flex_on = False
    holiday_on = False

    running_tasks = log_df[log_df['End_Time'] == 'RUNNING']
    active_count = len(running_tasks)
    
    if active_count > 0:
        st.markdown(f'<div style="position: fixed; bottom: 30px; left: 20px; background-color: #ff4b4b; color: white; padding: 8px 16px; border-radius: 20px; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); font-weight: bold; font-size: 16px; z-index: 9999; pointer-events: none; display: flex; align-items: center; justify-content: center;"><span style="font-size: 16px; margin-right: 6px; animation: pulse 1.5s infinite;">⏱️</span> {active_count}</div>', unsafe_allow_html=True)

    # --- TOP HEADER & SYNC (Always Visible) ---
    st.markdown(f'<h3 style="text-align: center; color: #888; margin-top: 0px;">{current_day} | {now.strftime("%I:%M %p")}</h3>', unsafe_allow_html=True)

    col1, col2 = st.columns([8, 2])
    with col2:
        if st.button("🔄 Sync", use_container_width=True):
            get_routine_data.clear()
            get_app_control_data.clear()
            get_activity_log.clear()
            get_future_tasks.clear()
            get_holidays.clear()
            get_payment_checklist.clear()
            get_must_do_tasks.clear()
            get_pre_tasks.clear()
            get_tracker_data.clear()
            st.toast("✅ Force Synced with Google Sheets!")
            time.sleep(1.0)
            st.rerun()

    # --- DYNAMIC APP LAUNCHPAD LOGIC ---
    base_app_list = [
        ("Money & Location", "money_location.py", "📍"),
        ("Money Utilities", "money_utilities.py", "💳"),
        ("Strong Tracker", "strong.py", "💪"),
        ("Project App", "project_app.py", "🚀"),
        ("Election Duty", "election_duty.py", "🗳️"),
        ("Monthly Tracker", "monthly_app.py", "📆"),
        ("Money Tracker", "money_tracker.py", "💵"),
        ("Sleep & Water", "sleep_water_app.py", "💧"),
        ("Backup Tracker", "backup_tracker_app.py", "💾"),
        ("Routine Audit", "routine_audit.py", "🔍"),
        ("Routine Editor", "routine_editor.py", "✏️"),
        ("MDM Returns", "mdm_return_log.py", "📦"),
        ("Video Manager", "bps_ytfb_videos.py", "🎬")
    ]
    
    active_apps_filter = []
    if not app_control_df.empty:
        for _, row in app_control_df.iterrows():
            try:
                start_str = str(row['Time_Slot_Start']).strip()
                end_str = str(row['Time_Slot_End']).strip()
                if not start_str or not end_str: continue

                start_t = datetime.strptime(start_str, '%H:%M').time()
                end_t = datetime.strptime('23:59:59', '%H:%M:%S').time() if end_str in ['0:00', '00:00', '24:00'] else datetime.strptime(end_str, '%H:%M').time()

                is_current = (start_t <= current_time <= end_t) if start_t <= end_t else (current_time >= start_t or current_time <= end_t)

                if is_current:
                    apps_raw = str(row['App']).split(',')
                    active_apps_filter.extend([a.strip() for a in apps_raw if a.strip()])
            except ValueError:
                continue

    filtered_app_list = [app for app in base_app_list if app[0] in active_apps_filter] if active_apps_filter else []

    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- SMART TABS: LAUNCHPAD BECOMES FIRST TAB IF ACTIVE ---
    if filtered_app_list:
        t_app, t_rout = st.tabs(["🚀 Scheduled Apps", "📋 Live Routine"])
    else:
        t_rout, t_app = st.tabs(["📋 Live Routine", "🚀 Scheduled Apps"])

    with t_app:
        if filtered_app_list:
            st.markdown('<h4 style="text-align: center; color: #333;">🚀 Scheduled Application Launchpad</h4>', unsafe_allow_html=True)
            for i in range(0, len(filtered_app_list), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(filtered_app_list):
                        app_name, file_name, icon = filtered_app_list[i + j]
                        last_str = get_app_time_str(app_name, tracker_data, now)
                        with cols[j]:
                            if st.button(f"{icon} {app_name}\\n(Last: {last_str})", key=f"app_{i+j}", use_container_width=True):
                                log_and_open_app(app_name, file_name, tracker_data, now)
        else:
            st.info("No external apps are scheduled for the current time slot.")

    # --- ALL ROUTINE HUB LOGIC INSIDE THE ROUTINE TAB ---
    with t_rout:
        # PRE-PROCESS ALL PAYMENTS 
        all_alert_pays = []
        if not payment_df.empty:
            def parse_pay_date(d_str):
                try: return pd.to_datetime(str(d_str).strip(), dayfirst=True).date()
                except: return pd.NaT
            
            payment_df['Due_Date_dt'] = payment_df['Due_Date'].apply(parse_pay_date)
            pending_payments = payment_df[~payment_df['Status'].str.strip().str.upper().isin(['PAID', 'DONE'])]
            for _, p_row in pending_payments.iterrows():
                if pd.notna(p_row['Due_Date_dt']):
                    days_until = (p_row['Due_Date_dt'] - now.date()).days
                    if days_until <= 3: all_alert_pays.append((days_until, p_row))

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
                end_t = datetime.strptime('23:59:59', '%H:%M:%S').time() if end_str in ['0:00', '00:00', '24:00'] else datetime.strptime(end_str, '%H:%M').time()

                is_current = (start_t <= current_time <= end_t) if start_t <= end_t else (current_time >= start_t or current_time <= end_t)

                if is_current:
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

        current_activity = scheduled_activity
        current_activity_start = scheduled_activity_start
        current_sub_activities = scheduled_sub_activities
        current_check_list = scheduled_check_list

        if current_activity in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY", "PEOPLE"]: color = "#ff4b4b" 
        elif current_activity in ["WORK", "REPORT", "TASK", "HOME TASK", "HOME UTILITIES"]: color = "#0068c9" 
        elif current_activity == "HEALTH": color = "#2e7b32" 
        elif current_activity in ["SLEEP", "PRE", "TEA", "OUT"]: color = "#ff9f36" 
        else: color = "#333333" 

        # --- COMPACT CURRENT ACTIVITY BOX ---
        st.markdown(f'<div style="text-align: center; background-color: #f8f9fa; border: 2px solid {color}; border-radius: 8px; padding: 8px; margin: 5px auto; max-width: 300px; box-shadow: 0px 2px 4px rgba(0,0,0,0.05);"><h3 style="margin: 0; font-size: 1.6rem; color: {color}; letter-spacing: 0.5px;">{current_activity}</h3></div>', unsafe_allow_html=True)

        if is_auto_holiday or holiday_on:
            if is_auto_holiday: st.markdown(f'<p style="text-align: center; color: #ff9f36; font-weight: bold; font-size: 1.1rem; margin-top: -5px;">🎉 {auto_occasion} (Holiday Schedule)</p>', unsafe_allow_html=True)
            else: st.markdown('<p style="text-align: center; color: #ff9f36; font-weight: bold; margin-top: -5px;">🎉 Running Custom Holiday Schedule</p>', unsafe_allow_html=True)

        if current_activity_start:
            dt_start = datetime.combine(now.date(), current_activity_start)
            dt_start = ist_timezone.localize(dt_start)
            if current_time < current_activity_start: dt_start -= timedelta(days=1)
            elapsed = now - dt_start
            eh, erem = divmod(int(elapsed.total_seconds()), 3600)
            em = erem // 60
            elapsed_text = f"{eh}h {em}m" if eh > 0 else f"{em}m"
            st.markdown(f'<h3 style="text-align: center; color: #555; margin-top: 0px; margin-bottom: 10px; font-weight: 400; font-size: 1.1rem;">⏱️ Elapsed: {elapsed_text}</h3>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="margin-bottom: 15px;"></div>', unsafe_allow_html=True)
            
        if next_activity not in ["NONE", "END OF DAY"]: st.markdown(f'<h4 style="text-align: center; color: #666; margin-bottom: 20px; font-weight: 400; font-size: 1.1rem;">Up Next: <b>{next_activity}</b> at {next_time_str}</h4>', unsafe_allow_html=True)
        elif next_activity == "END OF DAY": st.markdown('<h4 style="text-align: center; color: #666; margin-bottom: 20px; font-weight: 400; font-size: 1.1rem;">Up Next: Schedule Complete</h4>', unsafe_allow_html=True)

        # --- SIMPLIFIED DYNAMIC PENDING PAYMENTS EXPANDER ---
        if all_alert_pays:
            all_alert_pays.sort(key=lambda x: x[0])
            min_days = all_alert_pays[0][0]
            
            if min_days < 0:
                header_bg = "#d32f2f" 
                header_icon = "🔴"
                header_text = "OVERDUE PAYMENTS!"
            elif min_days == 0:
                header_bg = "#ef5350" 
                header_icon = "🚨"
                header_text = "PAYMENTS DUE TODAY!"
            elif min_days == 1:
                header_bg = "#f57c00" 
                header_icon = "🟠"
                header_text = "Payments Due Tomorrow"
            else:
                header_bg = "#ffb300" 
                header_icon = "🟡"
                header_text = f"Payments Due in {min_days} Days"
            
            box_html = f'<details style="background-color: #f8f9fa; border: 1px solid {header_bg}; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden;">'
            box_html += f'<summary style="background-color: {header_bg}; color: white; font-size: 16px; font-weight: bold; cursor: pointer; outline: none; padding: 10px; margin: 0;">{header_icon} {header_text} ({len(all_alert_pays)}) <span style="float:right;">▼</span></summary>'
            box_html += '<div style="padding: 10px;">'
            
            for i, (days_until, p_row) in enumerate(all_alert_pays):
                if days_until < 0:
                    day_str = f"Overdue by {abs(days_until)} days!"
                    item_bg = "#d32f2f" # Red
                elif days_until == 0:
                    day_str = "Due Today!"
                    item_bg = "#ef5350" # Light Red
                elif days_until == 1:
                    day_str = "Due Tomorrow!"
                    item_bg = "#f57c00" # Orange
                else:
                    day_str = f"Due in {days_until} days"
                    item_bg = "#ffb300" # Amber
                
                pad_bot = "margin-bottom: 8px;" if i < len(all_alert_pays) - 1 else "margin-bottom: 0px;"
                # Simplified Card: Only Bill Name and Due Date
                box_html += f'<div style="background-color: {item_bg}; color: white; padding: 8px 12px; border-radius: 6px; {pad_bot} box-shadow: 0 1px 3px rgba(0,0,0,0.1);"><strong style="font-size: 15px;">{p_row["Bill_Name"]} - {day_str}</strong></div>'
            
            box_html += "</div></details>"
            st.markdown(box_html, unsafe_allow_html=True)

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
                    
                    if str(r['Status']).strip().upper() in ['COMPLETED', 'CANCELED'] or any(formatted_task.upper() == str(x).strip().upper() for x in all_logged_items): continue
                        
                    if hours_until_due <= 24:
                        sec_diff = time_diff.total_seconds()
                        is_overdue = sec_diff < 0
                        abs_sec = abs(int(sec_diff))
                        
                        # Calculate Days, Hours, Minutes
                        d, h_rem = divmod(abs_sec, 86400)
                        h, m_rem = divmod(h_rem, 3600)
                        m = m_rem // 60
                        
                        time_parts = []
                        if d > 0: time_parts.append(f"{int(d)}d")
                        if h > 0 or d > 0: time_parts.append(f"{int(h)}h")
                        time_parts.append(f"{int(m)}m")
                        time_str = " ".join(time_parts)
                        
                        time_text = f"overdue by {time_str}" if is_overdue else f"due in {time_str}"
                        text_color = "#ff4b4b" if is_overdue and abs_sec >= 1800 else "#0068c9"
                        html_string = f"&gt; <b style='color: {text_color};'>{r['Task_Name']} ({r['Activity']})</b> {time_text}"
                        upcoming_ui_elements_raw.append((due_dt, r, html_string, is_overdue))
                        
                    if hours_until_due <= 0 and str(r['Activity']).strip().upper() == current_activity:
                        if r['Type'] == 'Sub-Activity': sub_list.append(formatted_task)
                        elif r['Type'] == 'Checklist': chk_list.append(formatted_task)
                except: continue

        if upcoming_ui_elements_raw:
            upcoming_ui_elements_raw.sort(key=lambda x: x[0])
            
            # Change header icon and text based on urgency
            most_urgent_dt = upcoming_ui_elements_raw[0][0]
            is_urgent_overdue = (most_urgent_dt - now).total_seconds() < 0
            if is_urgent_overdue:
                header_text = f"🔴 Upcoming Special Tasks - OVERDUE ({len(upcoming_ui_elements_raw)})"
            else:
                header_text = f"🟠 Upcoming Special Tasks ({len(upcoming_ui_elements_raw)})"
            
            with st.expander(header_text, expanded=False):
                for dt, r, html_text, is_overdue in upcoming_ui_elements_raw:
                    st.markdown(f'<p style="text-align: center; margin-bottom:5px; font-size:16px; color: #d84315;">{html_text}</p>', unsafe_allow_html=True)
                    
                    # RUN or MANAGE task columns
                    col_run, col_manage = st.columns(2)
                    with col_run:
                        if st.button("▶️ Run Task", key=f"run_sp_{r['row_index']}", use_container_width=True):
                            smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, str(r['Activity']).upper(), str(r['Task_Name']).strip(), "", "Started from Special Tasks"])
                            get_activity_log.clear() 
                            st.rerun()
                    with col_manage:
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
                                    smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), GS_FORMULA, str(r['Activity']).upper(), "", f"{r['Task_Name']} [RESCHEDULED]", f"Moved to {new_date.strftime('%Y-%m-%d')} {new_time}"])
                                    get_future_tasks.clear() 
                                    get_activity_log.clear() 
                                    st.rerun()
                            with tab_cancel:
                                col_r, col_b = st.columns([3, 1])
                                with col_r: cancel_reason = st.text_input("Reason", placeholder="Why are you cancelling?", key=f"rsn_{r['row_index']}", label_visibility="collapsed")
                                with col_b:
                                    if st.button("Confirm", key=f"cnf_{r['row_index']}", type="primary"):
                                        if cancel_reason.strip():
                                            fsheet = get_sheet("future_tasks")
                                            fsheet.update_cell(int(r['row_index']), 7, "Canceled")
                                            fsheet.update_cell(int(r['row_index']), 8, cancel_reason)
                                            smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), GS_FORMULA, str(r['Activity']).upper(), "", f"{r['Task_Name']} [CANCELED]", f"Cancel Reason: {cancel_reason}"])
                                            get_future_tasks.clear() 
                                            get_activity_log.clear() 
                                            st.rerun()
                    st.markdown('<hr style="margin-top:5px; margin-bottom:15px;">', unsafe_allow_html=True)

        future_holidays = holidays_df[holidays_df['Date_dt'].dt.date > now.date()].sort_values('Date_dt')
        if not future_holidays.empty:
            upcoming_hols = future_holidays.head(3)
            with st.expander(f"🌴 Upcoming Holidays ({len(upcoming_hols)})", expanded=False):
                for _, h_row in upcoming_hols.iterrows():
                    days_until = (h_row['Date_dt'].date() - now.date()).days
                    day_str = "Tomorrow!" if days_until == 1 else f"in {days_until} days"
                    st.markdown(f"**{h_row['Date_dt'].strftime('%b %d, %Y')}** - {h_row['Occasion']} *( {day_str} )*")

        # --- PRE TASKS FROM 'PRE' TAB ---
        if not pre_df.empty:
            valid_pres = pre_df[pre_df['Task Name'].str.strip() != '']
            if not valid_pres.empty:
                with st.expander(f"🌅 PRE ({len(valid_pres)})", expanded=False):
                    st.markdown('<p style="text-align: center; color: #888; font-size: 13px; margin-top:-10px;">Tap to start tracking</p>', unsafe_allow_html=True)
                    pre_cols = st.columns(2)
                    running_subs_upper = [str(x).strip().upper() for x in running_tasks['Sub_Activities'].tolist()]
                    for idx, row in valid_pres.iterrows():
                        p_task = str(row['Task Name']).strip()
                        p_cat = str(row['Main Category']).strip().upper() or "PRE"
                        with pre_cols[idx % 2]:
                            if p_task.upper() in running_subs_upper:
                                st.button(f"⏳ {p_task}", key=f"pre_run_{idx}", disabled=True, use_container_width=True)
                            elif st.button(f"▶️ {p_task}", key=f"pre_btn_{idx}", use_container_width=True):
                                smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, p_cat, p_task, "", "PRE Task"])
                                get_activity_log.clear()
                                st.rerun()

        # --- MUST DO TASKS ---
        if not must_do_df.empty:
            valid_must_dos = must_do_df[must_do_df['Task Name'].str.strip() != '']
            if not valid_must_dos.empty:
                with st.expander(f"⭐ Must Do Tasks ({len(valid_must_dos)})", expanded=False):
                    st.markdown('<p style="text-align: center; color: #888; font-size: 13px; margin-top:-10px;">Tap to start tracking</p>', unsafe_allow_html=True)
                    md_cols = st.columns(2)
                    running_subs_upper = [str(x).strip().upper() for x in running_tasks['Sub_Activities'].tolist()]
                    for idx, row in valid_must_dos.iterrows():
                        md_task = str(row['Task Name']).strip()
                        md_cat = str(row['Main Category']).strip().upper() or "WORK"
                        with md_cols[idx % 2]:
                            if md_task.upper() in running_subs_upper:
                                st.button(f"⏳ {md_task}", key=f"md_run_{idx}", disabled=True, use_container_width=True)
                            elif st.button(f"▶️ {md_task}", key=f"md_btn_{idx}", use_container_width=True):
                                smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, md_cat, md_task, "", "Must Do Task"])
                                get_activity_log.clear()
                                st.rerun()

        # --- EXPANDABLE TASKS & REMINDERS ---
        if chk_list:
            with st.expander(f"✅ Tasks & Reminders ({len(chk_list)})", expanded=True):
                today_logs = log_df[log_df['Date'] == today_str]
                today_logged_tasks = today_logs[today_logs['Activity'] == current_activity]['check_list'].tolist()
                
                for task in chk_list:
                    is_done = any(task.upper() == str(x).strip().upper() for x in (all_logged_items if "[Due:" in task else today_logged_tasks))
                    if "[Due:" in task and not is_done:
                        raw_task = task.split(" [Due:")[0].strip()
                        matches = future_df[(future_df['Task_Name'].str.strip() == raw_task) & (future_df['Type'] == 'Checklist')]
                        if not matches.empty and str(matches.iloc[0]['Status']).strip().upper() in ['COMPLETED', 'CANCELED']: is_done = True
                    
                    checked = st.checkbox(f"{task} (Last: {get_last_done_str(task, log_df, now, col_name='check_list')})", value=is_done, disabled=is_done, key=f"chk_{task}_{current_activity}")
                    if checked and not is_done:
                        smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), GS_FORMULA, current_activity, "", task, "Checked off"])
                        if "[Due:" in task:
                            matches = future_df[(future_df['Task_Name'].str.strip() == task.split(" [Due:")[0].strip()) & (future_df['Type'] == 'Checklist')]
                            if not matches.empty:
                                get_sheet("future_tasks").update_cell(int(matches.iloc[0]['row_index']), 7, "Completed") 
                                get_future_tasks.clear() 
                        get_activity_log.clear() 
                        st.rerun()

        # ==========================================
        # MULTI-TASKING LOGIC (LIVE TIMERS)
        # ==========================================
        if sub_list or active_count > 0:
            st.markdown("---")
            st.markdown('<h4 style="text-align: center; color: #333;">Tap to Track Activity</h4>', unsafe_allow_html=True)
            
            if active_count > 0:
                for idx, active_row in running_tasks.iterrows():
                    sheet_row = idx + 2 
                    display_name = str(active_row['Sub_Activities']) or str(active_row['Activity'])
                    
                    try:
                        dt_naive = datetime.strptime(f"{active_row['Date']} {active_row['Start_Time']}", "%Y-%m-%d %H:%M")
                        mins_elapsed = int((now - ist_timezone.localize(dt_naive)).total_seconds() // 60)
                    except: mins_elapsed = 0 
                    
                    cycle_minute = mins_elapsed % 30
                    pomodoro_count = (mins_elapsed // 30) + 1
                    current_state = "Focus" if cycle_minute < 25 else "Break"
                    task_id = f"task_{sheet_row}"
                    
                    if task_id in st.session_state.pomodoro_state and st.session_state.pomodoro_state[task_id] != current_state:
                        components.html("""<script>try {var ctx = new (window.AudioContext || window.webkitAudioContext)();function playBeep(freq, time, dur) {var osc = ctx.createOscillator();var gain = ctx.createGain();osc.connect(gain);gain.connect(ctx.destination);osc.frequency.value = freq;osc.type = "square";gain.gain.setValueAtTime(0.1, time);gain.gain.exponentialRampToValueAtTime(0.001, time + dur);osc.start(time);osc.stop(time + dur);}playBeep(600, ctx.currentTime, 0.2);playBeep(800, ctx.currentTime + 0.2, 0.3);} catch(e) {}</script>""", height=0, width=0)
                    st.session_state.pomodoro_state[task_id] = current_state

                    p_color, p_state, p_left, p_prog = ("#d84315", "🍅 Focus Time", 25 - cycle_minute, cycle_minute / 25.0) if current_state == "Focus" else ("#2e7b32", "☕ Break Time", 30 - cycle_minute, (cycle_minute - 25) / 5.0)
                    
                    st.markdown(f'<div style="background-color: #f8f9fa; border-left: 5px solid {p_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"><div style="display: flex; justify-content: space-between; align-items: center;"><strong style="font-size: 16px; color: #333;">⏳ {display_name}</strong><span style="color: #666; font-size: 14px;">Total: {mins_elapsed}m</span></div><div style="margin-top: 8px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;"><span style="color: {p_color}; font-weight: bold; font-size: 14px;">{p_state} (Cycle {pomodoro_count})</span><span style="color: #555; font-size: 13px; font-weight: bold;">{p_left}m left</span></div><div style="width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 6px;"><div style="width: {p_prog * 100}%; background-color: {p_color}; height: 6px; border-radius: 4px; transition: width 0.5s ease;"></div></div></div>', unsafe_allow_html=True)

                    col_stop, col_cancel = st.columns(2)
                    with col_stop:
                        if st.button("🛑 SAVE", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                            log_sheet = get_sheet("activity_log")
                            log_sheet.update_cell(sheet_row, 3, now.strftime('%H:%M')) 
                            log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                            if str(active_row['Notes']).strip() == "": log_sheet.update_cell(sheet_row, 8, "Auto-logged via Timer") 
                                
                            if "[Due:" in str(active_row['Sub_Activities']):
                                matches = future_df[(future_df['Task_Name'].str.strip() == str(active_row['Sub_Activities']).split(" [Due:")[0].strip()) & (future_df['Type'] == 'Sub-Activity')]
                                if not matches.empty:
                                    get_sheet("future_tasks").update_cell(int(matches.iloc[0]['row_index']), 7, "Completed") 
                                    get_future_tasks.clear()
                            get_activity_log.clear() 
                            st.rerun()

                    with col_cancel:
                        if st.button("❌ CANCEL", key=f"cancel_{sheet_row}", use_container_width=True):
                            get_sheet("activity_log").delete_rows(sheet_row)
                            get_activity_log.clear() 
                            st.rerun()
            
            avail_subs = [t for t in sub_list if t not in running_tasks['Sub_Activities'].tolist()]
            if avail_subs:
                st.markdown('<div style="margin-top: 15px; margin-bottom: 5px; color: #333;"><b>▶️ Routine Tasks:</b></div>', unsafe_allow_html=True)
                
                for i in range(0, len(avail_subs), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(avail_subs):
                            task = avail_subs[i+j]
                            with cols[j]:
                                if st.button(f"▶️ {task}" + ("" if "[Due:" in task else f"\n(Last: {get_last_done_str(task, log_df, now, col_name='Sub_Activities')})"), key=f"btn_{i+j}_{task}", use_container_width=True):
                                    smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, current_activity, task, "", "Auto-logged via Timer"])
                                    get_activity_log.clear() 
                                    st.rerun()

            # --- VISITOR TRACKER (Single Card) ---
            st.markdown('<div style="margin-top: 15px; margin-bottom: 5px; color: #ff4b4b;"><b>👥 Visitor Tracker:</b></div>', unsafe_allow_html=True)
            with st.container():
                st.markdown("<div style='background-color:#ffffff; padding:15px; border-radius:8px; border:1px solid #ddd; margin-bottom: 15px;'>", unsafe_allow_html=True)
                if st.button("⚡ Quick Start (Update Details Later)", use_container_width=True):
                    smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "PEOPLE", "VISITOR", "", "Update details later"])
                    get_activity_log.clear() 
                    st.rerun()

                st.markdown("<p style='text-align:center; font-size:12px; color:#888; margin: 12px 0;'>— OR ENTER DETAILS FIRST —</p>", unsafe_allow_html=True)
                
                col_mt1, col_mt2 = st.columns(2)
                with col_mt1: interaction_type = st.selectbox("Type", ["Attend Visitor", "Meet People"], key="live_mtg_type")
                extracted_names = [(val.split(" - ", 1)[-1].strip() if " - " in val else val.strip()) for val in log_df[log_df['Activity'] == 'PEOPLE']['Sub_Activities'].dropna().astype(str)]
                with col_mt2: person_type = st.selectbox("Person", ["-- New Person --"] + sorted(list(set([n for n in extracted_names if n]))), key="live_mtg_person")
                person_name = st.text_input("Name of New Person", key="live_mtg_new_name") if person_type == "-- New Person --" else person_type
                topic_talk = st.text_input("Topic", key="live_mtg_topic")
                purpose_visit = st.text_input("Purpose", key="live_mtg_purpose")
                
                if st.button("▶️ Start with Details", type="primary", use_container_width=True):
                    smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "PEOPLE", f"{interaction_type} - {(person_name.strip() if person_name else 'Unknown')}".upper(), "", f"Topic: {topic_talk} | Purpose: {purpose_visit}"])
                    get_activity_log.clear() 
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        # --- SCHEDULE FUTURE TASK ---
        with st.expander("🗓️ Schedule Future Task"):
            with st.form("schedule_future_form", clear_on_submit=True):
                f_act_list = [act for act in df['Activity'].unique() if act.strip()]
                f_act = st.selectbox("Parent Category", f_act_list, key="f_act")
                f_act_custom = st.text_input("New Parent Category (Leave blank to use selected above)", placeholder="Type custom category here...", key="f_act_custom")
                
                f_type = st.radio("Task Type", ["Checklist", "Sub-Activity"], horizontal=True, key="f_type")
                f_name = st.text_input("Task Details", placeholder="e.g., Pay Electricity Bill", key="f_name")
                time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
                col1, col2 = st.columns(2)
                with col1: f_date = st.date_input("Due Date", value=now.date(), key="f_date")
                with col2: f_time = datetime.strptime(st.selectbox("Due Time", options=time_opts, index=time_opts.index(clean_now.strftime('%H:%M')), key="f_time"), '%H:%M').time()
                    
                if st.form_submit_button("Schedule Task", use_container_width=True):
                    final_act = f_act_custom.strip().upper() if f_act_custom.strip() else f_act.strip().upper()
                    if f_name:
                        smart_append_row(get_sheet("future_tasks"), [f_date.strftime('%Y-%m-%d'), f_time.strftime('%H:%M'), final_act, f_type, f_name.strip(), "Personal", "Pending", ""])
                        get_future_tasks.clear() 
                        st.rerun()
                    else: st.error("Please enter task details.")

        # --- UPDATED MANUAL LOG SECTION WITH 1-MINUTE DROPDOWNS ---
        with st.expander("📝 Manual Log Activity"):
            unique_acts = sorted(list(set([a.strip().upper() for a in df['Activity'] if a.strip()])))
            log_date = st.date_input("Date", value=now.date(), key="log_date")
            
            col_act1, col_act2 = st.columns(2)
            with col_act1: 
                default_act_idx = unique_acts.index(current_activity) + 1 if current_activity in unique_acts else 0
                sel_act = st.selectbox("Activity", ["-- Type Custom --"] + unique_acts, index=default_act_idx, key="sel_act")
                log_activity = st.text_input("Type Custom Activity", key="txt_act") if sel_act == "-- Type Custom --" else sel_act
                
            with col_act2: 
                dependent_subs = []
                if log_activity in unique_acts:
                    filtered_df = df[df['Activity'].str.strip().str.upper() == log_activity]
                    sub_list = []
                    for s in filtered_df['Sub_Activities']:
                        sub_list.extend([x.strip().title() for x in str(s).split(',') if x.strip()])
                    dependent_subs = sorted(list(set(sub_list)))

                sel_sub = st.selectbox("Sub-Activity", ["-- None / Type Custom --"] + dependent_subs, index=0, key="sel_sub")
                log_sub_activity = st.text_input("Type Custom Sub-Activity", key="txt_sub") if sel_sub == "-- None / Type Custom --" else sel_sub
                if sel_sub == "-- None / Type Custom --" and not log_sub_activity: 
                    log_sub_activity = ""
                
            hours = [f"{i:02d}" for i in range(24)]
            minutes = [f"{i:02d}" for i in range(60)]
            curr_h = int(clean_now.strftime('%H'))
            curr_m = int(clean_now.strftime('%M'))
            
            col1, col2 = st.columns(2)
            with col1: 
                st.markdown('<div style="font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #333;">Started At (HH : MM)</div>', unsafe_allow_html=True)
                c_sh, c_sm = st.columns(2)
                s_hour = c_sh.selectbox("Start Hour", hours, index=curr_h, key="s_hour", label_visibility="collapsed")
                s_min = c_sm.selectbox("Start Min", minutes, index=curr_m, key="s_min", label_visibility="collapsed")
                
            with col2: 
                st.markdown('<div style="font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #333;">Ended At (HH : MM)</div>', unsafe_allow_html=True)
                c_eh, c_em = st.columns(2)
                e_hour = c_eh.selectbox("End Hour", hours, index=curr_h, key="e_hour", label_visibility="collapsed")
                e_min = c_em.selectbox("End Min", minutes, index=curr_m, key="e_min", label_visibility="collapsed")
            
            log_chk = st.text_input("Checklist Item (Optional)", key="log_chk")    
            log_notes = st.text_area("Notes", key="log_notes")
            
            if st.button("💾 Save to Activity Log", use_container_width=True, type="primary"):
                if log_activity:
                    smart_append_row(get_sheet("activity_log"), [
                        log_date.strftime('%Y-%m-%d'), 
                        f"{s_hour}:{s_min}", 
                        f"{e_hour}:{e_min}", 
                        GS_FORMULA, 
                        log_activity.upper().strip(), 
                        log_sub_activity.title().strip(), 
                        log_chk.strip(), 
                        log_notes
                    ])
                    get_activity_log.clear() 
                    st.success("Activity Logged!")
                    time.sleep(1.0)
                    st.rerun()
                else: 
                    st.error("Please provide an Activity.")

    # --- PERMANENT ALL APPS LAUNCHPAD (At the Bottom) ---
    st.markdown("---")
    with st.expander("🧩 All Applications Launchpad", expanded=not bool(filtered_app_list)):
        for i in range(0, len(base_app_list), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(base_app_list):
                    app_name, file_name, icon = base_app_list[i + j]
                    last_str = get_app_time_str(app_name, tracker_data, now)
                    with cols[j]:
                        if st.button(f"{icon} {app_name}\n(Last: {last_str})", key=f"all_app_{i+j}", use_container_width=True):
                            log_and_open_app(app_name, file_name, tracker_data, now)

except Exception as e: st.error(f"System Error: {e}")
