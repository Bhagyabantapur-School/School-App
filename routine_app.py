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
    log_df = get_activity_log() 
    future_df = get_future_tasks()
    holidays_df = get_holidays()
    payment_df = get_payment_checklist()
    must_do_df = get_must_do_tasks()
    tracker_data = get_tracker_data()
    
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

    st.markdown(f"<h3 style='text-align: center; color: #888; margin-top: 0px;'>{current_day} | {now.strftime('%I:%M %p')}</h3>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1: flex_on = st.toggle("🔀 Flex", key="flex_toggle")
    with col2: holiday_on = st.toggle("🎉 Holiday", key="holiday_toggle")
    with col3:
        if st.button("🔄 Sync", use_container_width=True):
            get_routine_data.clear()
            get_activity_log.clear()
            get_future_tasks.clear()
            get_holidays.clear()
            get_payment_checklist.clear()
            get_must_do_tasks.clear()
            get_tracker_data.clear()
            st.toast("✅ Force Synced with Google Sheets!")
            time.sleep(1.0)
            st.rerun()

    # --- APP LAUNCHPAD INJECTION ---
    st.markdown("---")
    st.markdown("<h4 style='text-align: center; color: #333;'>🚀 Application Launchpad</h4>", unsafe_allow_html=True)
    
    app_list = [
        ("Money & Location", "money_location.py", "📍"),
        ("Money Utilities", "money_utilities.py", "💳"),
        ("Strong Tracker", "strong.py", "💪"),
        ("Project App", "project_app.py", "🚀"),
        ("Election Duty", "election_duty.py", "🗳️"),
        ("Monthly Tracker", "monthly_app.py", "📆"),
        ("Money Tracker", "money_tracker.py", "💵"),
        ("Health Hub", "health_app.py", "❤️"),
        ("Backup Tracker", "backup_tracker_app.py", "💾"),
        ("Routine Audit", "routine_audit.py", "🔍"),
        ("Routine Editor", "routine_editor.py", "✏️"),
        ("MDM Returns", "mdm_return_log.py", "📦"),
        ("Video Manager", "bps_ytfb_videos.py", "🎬")
    ]
    
    app_cols = st.columns(3)
    for idx, (app_name, file_name, icon) in enumerate(app_list):
        last_str = get_app_time_str(app_name, tracker_data, now)
        with app_cols[idx % 3]:
            if st.button(f"{icon} {app_name}\n(Last: {last_str})", key=f"app_{idx}", use_container_width=True):
                log_and_open_app(app_name, file_name, tracker_data, now)
    st.markdown("---")

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
                if days_until <= 1: all_alert_pays.append((days_until, p_row))

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

    if flex_on:
        unique_activities = sorted(list(set([act.strip().upper() for act in df['Activity'] if act.strip()])))
        if "FREE TIME" not in unique_activities: unique_activities.append("FREE TIME")
        current_activity = st.selectbox("What are you actually doing right now?", unique_activities, key="flex_sel")
        matched_rows = df[df['Activity'].str.strip().str.upper() == current_activity]
        agg_subs, agg_chks = [], []
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
        if is_auto_holiday: st.markdown(f"<p style='text-align: center; color: #ff9f36; font-weight: bold; font-size: 1.1rem; margin-top: -10px;'>🎉 {auto_occasion} (Holiday Schedule Active)</p>", unsafe_allow_html=True)
        else: st.markdown("<p style='text-align: center; color: #ff9f36; font-weight: bold; margin-top: -10px;'>🎉 Running Custom Holiday Schedule</p>", unsafe_allow_html=True)

    if current_activity_start and not flex_on:
        dt_start = datetime.combine(now.date(), current_activity_start)
        dt_start = ist_timezone.localize(dt_start)
        if current_time < current_activity_start: dt_start -= timedelta(days=1)
        elapsed = now - dt_start
        eh, erem = divmod(int(elapsed.total_seconds()), 3600)
        em = erem // 60
        elapsed_text = f"{eh}h {em}m" if eh > 0 else f"{em}m"
        st.markdown(f"<h3 style='text-align: center; color: #555; margin-top: 0px; margin-bottom: 10px; font-weight: 400;'>⏱️ Elapsed: {elapsed_text}</h3>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
        
    if next_activity == "FLEX MODE ACTIVE": st.markdown(f"<h4 style='text-align: center; color: #e65100; margin-bottom: 20px; font-weight: 400;'>⚠️ Schedule Paused - Logging Custom Activity</h4>", unsafe_allow_html=True)
    elif next_activity not in ["NONE", "END OF DAY"]: st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: <b>{next_activity}</b> at {next_time_str}</h4>", unsafe_allow_html=True)
    elif next_activity == "END OF DAY": st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: Schedule Complete</h4>", unsafe_allow_html=True)

    if all_alert_pays:
        all_alert_pays.sort(key=lambda x: x[0])
        st.markdown("<br>", unsafe_allow_html=True)
        box_html = "<div style='background-color: #f8f9fa; border: 1px solid #e0e0e0; padding: 15px; margin-bottom: 15px; border-radius: 8px;'><h4 style='color: #1e88e5; margin-top: 0px; margin-bottom: 15px; border-bottom: 2px solid #1e88e5; padding-bottom: 8px;'>🚨 Pending Payments</h4>"
        for i, (days_until, p_row) in enumerate(all_alert_pays):
            day_str = f"Overdue by {abs(days_until)} days!" if days_until < 0 else ("Due Today!" if days_until == 0 else "Due Tomorrow!")
            bg_color = "#d32f2f" if days_until < 0 else ("#ef5350" if days_until == 0 else "#f57c00")
            pad_bot = "margin-bottom: 10px;" if i < len(all_alert_pays) - 1 else "margin-bottom: 0px;"
            box_html += f"<div style='background-color: {bg_color}; color: white; padding: 12px; border-radius: 6px; {pad_bot}'><strong style='font-size: 16px;'>{p_row['Bill_Name']} ({p_row['Type']}) - {day_str}</strong><br><span style='font-size: 14px; opacity: 0.9;'>Est: ₹{p_row['Est_Amount']} | Fund: {p_row['Fund']} | A/c: {p_row['Account']}</span></div>"
        box_html += "</div>"
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
                    h, rem = divmod(abs_sec, 3600)
                    m = rem // 60
                    time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
                    
                    time_text = f"overdue by {time_str}" if is_overdue else f"due in {time_str}"
                    text_color = "#ff4b4b" if is_overdue and abs_sec >= 1800 else "#0068c9"
                    html_string = f"&gt; <b style='color: {text_color};'>{r['Task_Name']} ({r['Activity']})</b> {time_text}"
                    upcoming_ui_elements_raw.append((due_dt, r, html_string))
                    
                if hours_until_due <= 0 and str(r['Activity']).strip().upper() == current_activity:
                    if r['Type'] == 'Sub-Activity': sub_list.append(formatted_task)
                    elif r['Type'] == 'Checklist': chk_list.append(formatted_task)
            except: continue

    if upcoming_ui_elements_raw:
        upcoming_ui_elements_raw.sort(key=lambda x: x[0])
        with st.expander(f"⏳ Upcoming Special Tasks ({len(upcoming_ui_elements_raw)})", expanded=False):
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
                st.markdown("<hr style='margin-top:5px; margin-bottom:15px;'>", unsafe_allow_html=True)

    future_holidays = holidays_df[holidays_df['Date_dt'].dt.date > now.date()].sort_values('Date_dt')
    if not future_holidays.empty:
        upcoming_hols = future_holidays.head(3)
        with st.expander(f"🌴 Upcoming Holidays ({len(upcoming_hols)})", expanded=False):
            for _, h_row in upcoming_hols.iterrows():
                days_until = (h_row['Date_dt'].date() - now.date()).days
                day_str = "Tomorrow!" if days_until == 1 else f"in {days_until} days"
                st.markdown(f"**{h_row['Date_dt'].strftime('%b %d, %Y')}** - {h_row['Occasion']} *( {day_str} )*")

    if not must_do_df.empty:
        valid_must_dos = must_do_df[must_do_df['Task Name'].str.strip() != '']
        if not valid_must_dos.empty:
            with st.expander(f"⭐ Must Do Tasks ({len(valid_must_dos)})", expanded=False):
                st.markdown("<p style='text-align: center; color: #888; font-size: 13px; margin-top:-10px;'>Tap to start tracking</p>", unsafe_allow_html=True)
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

    if chk_list:
        st.markdown("---")
        st.markdown("<h4 style='text-align: center; color: #333;'>✅ Tasks & Reminders</h4>", unsafe_allow_html=True)
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
        st.markdown("<h4 style='text-align: center; color: #333;'>Tap to Track Activity</h4>", unsafe_allow_html=True)
        
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
            st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #333;'><b>▶️ Routine Tasks:</b></div>", unsafe_allow_html=True)
            cols = st.columns(3)
            for idx, task in enumerate(avail_subs):
                with cols[idx % 3]:
                    if st.button(f"▶️ {task}" + ("" if "[Due:" in task else f"\n(Last: {get_last_done_str(task, log_df, now, col_name='Sub_Activities')})"), key=f"btn_{idx}_{task}", use_container_width=True):
                        smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, current_activity, task, "", "Auto-logged via Timer"])
                        get_activity_log.clear() 
                        st.rerun()

        st.markdown("<div style='margin-top: 15px; margin-bottom: 5px; color: #ff4b4b;'><b>👥 Meeting / Visitor Tracker:</b></div>", unsafe_allow_html=True)
        if st.button("⚡ Quick Start (Update Details Later)", use_container_width=True):
            smart_append_row(get_sheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "PEOPLE", "MEETING / VISITOR", "", "Update details later"])
            get_activity_log.clear() 
            st.rerun()

        with st.expander("📝 Enter Details Before Starting", expanded=False):
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

    st.markdown("---")
    st.markdown("<h4 style='text-align: center; color: #555; margin-bottom: 20px;'>📊 Today's Actual Productivity</h4>", unsafe_allow_html=True)
    today_logs = log_df[(log_df['Date'] == today_str) & (log_df['Duration'] != 'RUNNING')].copy()
    if not today_logs.empty:
        today_logs['Total_Minutes'] = today_logs['Duration'].apply(parse_duration_to_minutes)
        summary = today_logs.groupby('Activity')['Total_Minutes'].sum().sort_values(ascending=False)
        cols = st.columns(min(len(summary), 3))
        for col_idx, (act, total_mins) in enumerate(summary.items()):
            with cols[col_idx % 3]: st.metric(label=act, value=f"{int(total_mins // 60)}:{int(total_mins % 60):02d}")
    else: st.markdown("<p style='text-align: center; color: #888;'>No completed activities logged yet.</p>", unsafe_allow_html=True)
    
    with st.expander("🗓️ Schedule Future Task"):
        with st.form("schedule_future_form", clear_on_submit=True):
            f_act = st.selectbox("Parent Category", [act for act in df['Activity'].unique() if act.strip()], key="f_act")
            f_type = st.radio("Task Type", ["Checklist", "Sub-Activity"], horizontal=True, key="f_type")
            f_entity = st.selectbox("Entity", ["Personal", "School", "People"], key="f_entity")
            f_name = st.text_input("Task Details", placeholder="e.g., Pay Electricity Bill", key="f_name")
            time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
            col1, col2 = st.columns(2)
            with col1: f_date = st.date_input("Due Date", value=now.date(), key="f_date")
            with col2: f_time = datetime.strptime(st.selectbox("Due Time", options=time_opts, index=time_opts.index(clean_now.strftime('%H:%M')), key="f_time"), '%H:%M').time()
                
            if st.form_submit_button("Schedule Task", use_container_width=True):
                if f_name:
                    smart_append_row(get_sheet("future_tasks"), [f_date.strftime('%Y-%m-%d'), f_time.strftime('%H:%M'), f_act.upper().strip(), f_type, f_name.strip(), f_entity, "Pending", ""])
                    get_future_tasks.clear() 
                    st.rerun()
                else: st.error("Please enter task details.")

    with st.expander("📝 Manual Log Activity"):
        with st.form("log_activity_form", clear_on_submit=True):
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
                    smart_append_row(get_sheet("activity_log"), [log_date.strftime('%Y-%m-%d'), log_start.strftime('%H:%M'), log_end.strftime('%H:%M'), GS_FORMULA, log_activity.upper().strip(), log_sub_activity.upper().strip(), log_chk.strip(), log_notes])
                    get_activity_log.clear() 
                    st.rerun()
                else: st.error("Please enter a Main Category.")

except Exception as e: st.error(f"System Error: {e}")
