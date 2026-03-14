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
    input[type="text"] {font-size: 16px;}
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

def get_sheet():
    client = init_connection()
    return client.open("MY ROUTINE 2026").sheet1

# --- THE FIX IS HERE ---
@st.cache_data(ttl=60) 
def get_routine_data():
    sheet = get_sheet()
    # Pull raw values to bypass the duplicate/empty header crash
    data = sheet.get_all_values()
    
    # Convert to DataFrame (Row 0 is headers, Row 1+ is data)
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Force the app to only look at the first 5 columns (ignoring accidental blank columns)
    df = df.iloc[:, :5]
    
    # Rename them explicitly to guarantee no errors
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity"]
    
    # Drop any completely empty rows that might have snuck in
    df = df[df["Day"].astype(str).str.strip() != ""]
    
    return df
# -----------------------

try:
    df = get_routine_data()
    
    # 3. Live Time Tracking (IST)
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    
    current_day = now.strftime('%A')
    current_time = now.time()

    # Top clock display
    st.markdown(f"<h3 style='text-align: center; color: #888;'>{current_day} | {now.strftime('%I:%M %p')}</h3>", unsafe_allow_html=True)

    current_activity = "FREE TIME"
    next_activity = "NONE"
    next_time_str = ""

    # Filter data for today only to make finding the "Next" activity easier
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

            # Check if we are currently in this activity
            if start_t <= current_time <= end_t:
                current_activity = str(row['Activity']).strip().upper()
                
                # Check what is next
                if i + 1 < len(today_schedule):
                    next_row = today_schedule[i+1]
                    next_activity = str(next_row['Activity']).strip().upper()
                    next_start_time = datetime.strptime(str(next_row['Start_Time']).strip(), '%H:%M')
                    next_time_str = next_start_time.strftime('%I:%M %p')
                else:
                    next_activity = "END OF DAY"
                break
                
            # If we are in FREE TIME (before this activity starts)
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

    # Main Activity Display 
    st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 30px; margin-bottom: 10px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

    # Up Next Subtitle Display
    if next_activity not in ["NONE", "END OF DAY"]:
        st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 40px; font-weight: 400;'>Up Next: <b>{next_activity}</b> at {next_time_str}</h4>", unsafe_allow_html=True)
    elif next_activity == "END OF DAY":
        st.markdown(f"<h4 style='text-align: center; color: #666; margin-bottom: 40px; font-weight: 400;'>Up Next: Schedule Complete</h4>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='margin-bottom: 40px;'></div>", unsafe_allow_html=True)

    # 6. Editor Expander
    with st.expander("✏️ Quick Add / Edit Routine"):
        with st.form("edit_routine_form", clear_on_submit=True):
            st.markdown("### Add New Time Slot")
            
            days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            col1, col2 = st.columns(2)
            with col1:
                input_day = st.selectbox("Day", days_of_week, index=days_of_week.index(current_day))
            with col2:
                input_activity = st.text_input("Activity (e.g., WORK, HEALTH)")
            
            col3, col4 = st.columns(2)
            with col3:
                input_start = st.time_input("Start Time", value=now.time())
            with col4:
                input_end = st.time_input("End Time", value=now.time())
                
            submitted = st.form_submit_button("Update Sheet", use_container_width=True)
            
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

                    sheet = get_sheet()
                    sheet.append_row([input_day, start_str, end_str, duration_str, input_activity.upper()])
                    
                    st.cache_data.clear()
                    st.success(f"Added '{input_activity.upper()}' to {input_day}!")
                    
                    # Force instant reload to show the change immediately
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please enter an activity name.")

except Exception as e:
    st.error(f"System Error: {e}")
