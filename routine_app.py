import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time
from streamlit_autorefresh import st_autorefresh

# 1. Configuration
st.set_page_config(page_title="Live Routine", page_icon="⏱️", layout="centered")

# Auto-Refresh every 60 seconds
st_autorefresh(interval=60000, key="routine_refresh")

# Hide standard Streamlit menus for a clean interface
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    input[type="text"], textarea {font-size: 16px;}
    div[data-testid="metric-container"] {text-align: center; background-color: #f0f2f6; padding: 10px; border-radius: 10px;}
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
    df = df.iloc[:, :5]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity"]
    df = df[df["Day"].astype(str).str.strip() != ""]
    return df

@st.cache_data(ttl=60)
def get_activity_log():
    sheet = get_sheet("activity_log")
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Notes"])
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

try:
    df = get_routine_data()
    
    # 3. Live Time Tracking (IST)
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    
    # Clean the current time so it doesn't carry seconds/microseconds into the input fields
    clean_now = now.replace(second=0, microsecond=0).time()
    
    current_day = now.strftime('%A')
    current_time = now.time()

    # Top clock display
    st.markdown(f"<h3 style='text-align: center; color: #888;'>{current_day} | {now.strftime('%I:%M %p')}</h3>", unsafe_allow_html=True)

    current_activity = "FREE TIME"
    next_activity = "NONE"
    next_time_str = ""

    today_schedule = []
    for _, row in df.iterrows():
        if str(row.get('Day')).strip() == current_day:
            today_schedule.append(row)

    # 4. Match current time and find Up Next
    for i, row in enumerate(today_schedule):
        try:
            start_str = str(row['Start_Time']).strip()
            end_str = str(row['End_Time']).strip()
            
            start_t = datetime.strptime(start_str, '%H:%M').time()
            if end_str == '0:00':
                end_t = datetime.strptime('23:59:59', '%H:%M:%S').time()
            else:
                end_t = datetime.strptime(end_str, '%H:%M').time()

            if start_t <= current_time <= end_t:
                current_activity = str(row['Activity']).strip().upper()
                
                if i + 1 < len(today_schedule):
                    next_row = today_schedule[i+1]
                    next_activity = str(next_row['Activity']).strip().upper()
                    next_start_time = datetime.strptime(str(next_row['Start_Time']).strip(), '%H:%M')
                    next_time_str = next_start_time.strftime('%I:%M %p')
                else:
                    next_activity = "END OF DAY"
                break
                
            elif current_time < start_t and current_activity == "FREE TIME":
                next_activity = str(row['Activity']).strip().upper()
                next_start_time = datetime.strptime(start_str, '%H:%M')
                next_time_str = next_start_time.strftime('%I:%M %p')
                break
                
        except ValueError:
            continue

    # 5. Dynamic UI Coloring
    if current_activity in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY"]:
        color = "#ff4b4b" 
    elif current_activity in ["WORK", "REPORT", "TASK"]:
        color = "#0068c9" 
    elif current_activity == "HEALTH":
        color = "#2e7b32" 
    elif current_activity in ["SLEEP", "PRE", "TEA", "OUT"]:
        color = "#ff9f36" 
    else:
        color = "#333333" 

    # Main Activity & Up Next
    st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 30px; margin-bottom: 10px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

    if next_activity not in ["NONE", "END OF DAY"]:
        st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 30px; font-weight: 400;'>Up Next: <b>{next_activity}</b> at {next_time_str}</h4>", unsafe_allow_html=True)
    elif next_activity == "END OF DAY":
        st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 30px; font-weight: 400;'>Up Next: Schedule Complete</h4>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)


    # 6. FEATURE: Daily Productivity Summary
    st.markdown("---")
    st.markdown("<h4 style='text-align: center; color: #555; margin-bottom: 20px;'>📊 Today's Productivity</h4>", unsafe_allow_html=True)
    
    log_df = get_activity_log()
    today_str = now.strftime('%Y-%m-%d')
    today_logs = log_df[log_df['Date'] == today_str].copy()
    
    if not today_logs.empty:
        # Convert the duration to total minutes to add them correctly
        def parse_duration_to_minutes(dur_str):
            try:
                h, m = map(int, str(dur_str).split(':'))
                return (h * 60) + m
            except:
                return 0
                
        today_logs['Total_Minutes'] = today_logs['Duration'].apply(parse_duration_to_minutes)
        summary = today_logs.groupby('Activity')['Total_Minutes'].sum().sort_values(ascending=False)
        
        cols = st.columns(min(len(summary), 3))
        col_idx = 0
        for act, total_mins in summary.items():
            # Convert the total minutes back to H:MM format for display
            hours, remainder_mins = divmod(total_mins, 60)
            display_time = f"{int(hours)}:{int(remainder_mins):02d}"
            
            with cols[col_idx % 3]:
                st.metric(label=act, value=display_time)
            col_idx += 1
    else:
        st.markdown("<p style='text-align: center; color: #888;'>No activities logged yet today.</p>", unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)


    # 7. FEATURE: Daily Activity Logger
    with st.expander("📝 Log Completed Activity"):
        with st.form("log_activity_form", clear_on_submit=True):
            st.markdown("### Record What You Did")
            
            log_date = st.date_input("Date", value=now.date(), key="log_date")
            log_activity = st.text_input("Activity Performed", value=current_activity if current_activity != "FREE TIME" else "", key="log_activity")
            
            col1, col2 = st.columns(2)
            with col1:
                log_start = st.time_input("Started At", value=clean_now, key="log_start")
            with col2:
                log_end = st.time_input("Ended At", value=clean_now, key="log_end")
                
            log_notes = st.text_area("Notes / Remarks (Optional)", key="log_notes")
            
            log_submitted = st.form_submit_button("Save to Activity Log", use_container_width=True)
            
            if log_submitted:
                if log_activity:
                    start_dt = datetime.combine(log_date, log_start)
                    end_dt = datetime.combine(log_date, log_end)
                    if end_dt < start_dt:
                        end_dt = end_dt.replace(day=end_dt.day + 1)
                    duration_td = end_dt - start_dt
                    hours, remainder = divmod(duration_td.seconds, 3600)
                    minutes = remainder // 60
                    duration_str = f"{hours}:{minutes:02d}"

                    log_sheet = get_sheet("activity_log")
                    log_sheet.append_row([
                        log_date.strftime('%Y-%m-%d'), 
                        log_start.strftime('%H:%M'), 
                        log_end.strftime('%H:%M'), 
                        duration_str, 
                        log_activity.upper(), 
                        log_notes
                    ])
                    
                    st.cache_data.clear()
                    st.success("Activity logged successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please enter an activity name.")


    # 8. FEATURE: Routine Editor
    with st.expander("✏️ Update Master Schedule"):
        with st.form("edit_routine_form", clear_on_submit=True):
            st.markdown("### Add to Routine Master")
            
            days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            col1, col2 = st.columns(2)
            with col1:
                input_day = st.selectbox("Day", days_of_week, index=days_of_week.index(current_day), key="master_day")
            with col2:
                input_activity = st.text_input("Routine Category (e.g., WORK, HEALTH)", key="master_activity")
            
            col3, col4 = st.columns(2)
            with col3:
                input_start = st.time_input("Schedule Start Time", value=clean_now, key="master_start")
            with col4:
                input_end = st.time_input("Schedule End Time", value=clean_now, key="master_end")
                
            submitted = st.form_submit_button("Update Master Sheet", use_container_width=True)
            
            if submitted:
                if input_activity:
                    start_str = input_start.strftime('%H:%M')
                    end_str = input_end.strftime('%H:%M')
                    
                    start_dt = datetime.combine(now.date(), input_start)
                    end_dt = datetime.combine(now.date(), input_end)
                    if end_dt < start_dt:
                        end_dt = end_dt.replace(day=end_dt.day + 1)
                    duration_td = end_dt - start_dt
                    hours, remainder = divmod(duration_td.seconds, 3600)
                    minutes = remainder // 60
                    duration_str = f"{hours}:{minutes:02d}"

                    routine_sheet = get_sheet("routine_master")
                    routine_sheet.append_row([input_day, start_str, end_str, duration_str, input_activity.upper()])
                    
                    st.cache_data.clear()
                    st.success(f"Added '{input_activity.upper()}' to {input_day}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please enter an activity category.")

except Exception as e:
    st.error(f"System Error: {e}")
