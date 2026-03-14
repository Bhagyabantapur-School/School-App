import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time
from streamlit_autorefresh import st_autorefresh

# 1. Configuration & Session State Init
st.set_page_config(page_title="Live Routine", page_icon="⏱️", layout="centered")

# Initialize the active task tracker to hold BOTH main and sub activities
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
    
    if df.shape[1] < 6:
        for _ in range(6 - df.shape[1]):
            df[df.shape[1]] = ""
            
    df = df.iloc[:, :6]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities"]
    
    df = df[df["Day"].astype(str).str.strip() != ""]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

@st.cache_data(ttl=60)
def get_activity_log():
    sheet = get_sheet("activity_log")
    data = sheet.get_all_values()
    
    # Updated to handle 7 columns (including Sub_Activities)
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "Notes"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    
    if df.shape[1] < 7:
        for _ in range(7 - df.shape[1]):
            df[df.shape[1]] = ""
            
    df = df.iloc[:, :7]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "Notes"]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

def parse_duration_to_minutes(dur_str):
    try:
        h, m = map(int, str(dur_str).strip().split(':'))
        return (h * 60) + m
    except:
        return 0

try:
    df = get_routine_data()
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    clean_now = now.replace(second=0, microsecond=0).time()
    
    current_day = now.strftime('%A')
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

        today_schedule = df[df['Day'].str.strip() == current_day].to_dict('records')

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
                    current_sub_activities = str(row.get('Sub_Activities', '')).strip()
                    
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

        st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 30px; margin-bottom: 10px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

        if next_activity not in ["NONE", "END OF DAY"]:
            st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: <b>{next_activity}</b> at {next_time_str}</h4>", unsafe_allow_html=True)
        elif next_activity == "END OF DAY":
            st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 20px; font-weight: 400;'>Up Next: Schedule Complete</h4>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # --- ONE CLICK TRACKER (START/STOP) ---
        sub_list = [s.strip() for s in current_sub_activities.split(',') if s.strip()]
        
        if sub_list or st.session_state.active_main_task:
            st.markdown("---")
            st.markdown("<h4 style='text-align: center; color: #333;'>Tap to Track Activity</h4>", unsafe_allow_html=True)
            
            # Display active task status
            if st.session_state.active_main_task:
                elapsed_time = now - st.session_state.active_start_time
                mins_elapsed = elapsed_time.seconds // 60
                display_name = st.session_state.active_sub_task if st.session_state.active_sub_task else st.session_state.active_main_task
                
                st.info(f"⏳ **In Progress:** {display_name} (Running for {mins_elapsed} min)")
                
                if st.button(f"🛑 STOP & SAVE {display_name}", use_container_width=True, type="primary"):
                    end_time_log = now.time()
                    start_time_log = st.session_state.active_start_time.time()
                    log_date = now.date()
                    
                    hours, remainder = divmod(elapsed_time.seconds, 3600)
                    minutes = remainder // 60
                    duration_str = f"{hours}:{minutes:02d}"

                    # Write 7 columns to the activity_log
                    log_sheet = get_sheet("activity_log")
                    log_sheet.append_row([
                        log_date.strftime('%Y-%m-%d'), 
                        start_time_log.strftime('%H:%M'), 
                        end_time_log.strftime('%H:%M'), 
                        duration_str, 
                        st.session_state.active_main_task, 
                        st.session_state.active_sub_task,
                        "Auto-logged via One-Click Timer"
                    ])
                    
                    st.session_state.active_main_task = None
                    st.session_state.active_sub_task = None
                    st.session_state.active_start_time = None
                    st.cache_data.clear()
                    st.success("Activity logged successfully!")
                    time.sleep(1)
                    st.rerun()

            # Display grid of sub-activities
            elif sub_list:
                cols = st.columns(3)
                for idx, task in enumerate(sub_list):
                    with cols[idx % 3]:
                        if st.button(f"▶️ {task}", key=f"btn_{task}", use_container_width=True):
                            # Lock in both Main Activity and Sub Activity
                            st.session_state.active_main_task = current_activity
                            st.session_state.active_sub_task = task
                            st.session_state.active_start_time = now
                            st.rerun()

        st.markdown("---")
        
        # Today's Productivity Metrics
        st.markdown("<h4 style='text-align: center; color: #555; margin-bottom: 20px;'>📊 Today's Actual Productivity</h4>", unsafe_allow_html=True)
        log_df = get_activity_log()
        today_str = now.strftime('%Y-%m-%d')
        today_logs = log_df[log_df['Date'] == today_str].copy()
        
        if not today_logs.empty:
            today_logs['Total_Minutes'] = today_logs['Duration'].apply(parse_duration_to_minutes)
            # The summary groups by Main Activity to keep the dashboard clean
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
            st.markdown("<p style='text-align: center; color: #888;'>No activities logged yet today.</p>", unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)

        # Manual Log Form
        with st.expander("📝 Manual Log Activity"):
            with st.form("log_activity_form", clear_on_submit=True):
                st.markdown("### Manually Record Time")
                log_date = st.date_input("Date", value=now.date(), key="log_date")
                
                # Split inputs for Main and Sub activity
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    log_activity = st.text_input("Main Category", value=current_activity if current_activity != "FREE TIME" else "", key="log_activity")
                with col_act2:
                    log_sub_activity = st.text_input("Sub-Activity", placeholder="e.g., YOGA", key="log_sub_activity")
                    
                col1, col2 = st.columns(2)
                with col1:
                    log_start = st.time_input("Started At", value=clean_now, key="log_start")
                with col2:
                    log_end = st.time_input("Ended At", value=clean_now, key="log_end")
                log_notes = st.text_area("Notes", key="log_notes")
                
                if st.form_submit_button("Save to Activity Log", use_container_width=True):
                    if log_activity:
                        start_dt = datetime.combine(log_date, log_start)
                        end_dt = datetime.combine(log_date, log_end)
                        if end_dt < start_dt: end_dt = end_dt.replace(day=end_dt.day + 1)
                        duration_td = end_dt - start_dt
                        h, m = divmod(duration_td.seconds, 3600)
                        
                        # Save 7 columns to the log
                        log_sheet = get_sheet("activity_log")
                        log_sheet.append_row([
                            log_date.strftime('%Y-%m-%d'), 
                            log_start.strftime('%H:%M'), 
                            log_end.strftime('%H:%M'), 
                            f"{h}:{m//60:02d}", 
                            log_activity.upper().strip(), 
                            log_sub_activity.upper().strip(),
                            log_notes
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
        st.markdown("<p style='text-align: center; color: #888; font-size: 14px; margin-bottom: 20px;'>Tap any cell to edit. Times will open your phone's clock dial.</p>", unsafe_allow_html=True)
        
        today_full_df = df[df['Day'].str.strip() == current_day].copy()
        
        if not today_full_df.empty:
            edit_df = today_full_df[['Start_Time', 'End_Time', 'Activity', 'Sub_Activities']].copy()
            
            def convert_to_time(t_str):
                try:
                    if t_str.strip() == '0:00': return datetime.strptime('00:00', '%H:%M').time()
                    return datetime.strptime(t_str.strip(), '%H:%M').time()
                except:
                    return datetime.strptime('00:00', '%H:%M').time()

            edit_df['Start_Time'] = edit_df['Start_Time'].apply(convert_to_time)
            edit_df['End_Time'] = edit_df['End_Time'].apply(convert_to_time)
            
            edited_schedule = st.data_editor(
                edit_df,
                column_config={
                    "Start_Time": st.column_config.TimeColumn("Start", format="HH:mm", step=60, required=True),
                    "End_Time": st.column_config.TimeColumn("End", format="HH:mm", step=60, required=True),
                    "Activity": st.column_config.TextColumn("Activity", required=True),
                    "Sub_Activities": st.column_config.TextColumn("Sub List (comma sep.)")
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
                        
                        new_rows.append([current_day, start_str, end_str, duration_str, str(row['Activity']).strip().upper(), sub_act])

                    full_df = df.copy()
                    other_days_df = full_df[full_df['Day'].str.strip() != current_day]
                    new_today_df = pd.DataFrame(new_rows, columns=["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities"])
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
