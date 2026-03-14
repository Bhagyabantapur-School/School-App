import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# Configuration
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

# Database Connection
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

@st.cache_data(ttl=60) 
def get_routine_data():
    sheet = get_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

try:
    df = get_routine_data()
    
    # Live Time Tracking (IST)
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    
    current_day = now.strftime('%A')
    current_time = now.time()

    st.markdown(f"<h3 style='text-align: center; color: #888;'>{current_day} | {now.strftime('%I:%M %p')}</h3>", unsafe_allow_html=True)

    current_activity = "FREE TIME"

    for _, row in df.iterrows():
        if str(row.get('Day')).strip() == current_day:
            try:
                start_t = datetime.strptime(str(row['Start_Time']).strip(), '%H:%M').time()
                end_str = str(row['End_Time']).strip()
                
                if end_str == '0:00':
                    end_t = datetime.strptime('23:59:59', '%H:%M:%S').time()
                else:
                    end_t = datetime.strptime(end_str, '%H:%M').time()

                if start_t <= current_time <= end_t:
                    current_activity = str(row['Activity']).strip().upper()
                    break
            except ValueError:
                continue

    # Dynamic UI Coloring
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

    st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 30px; margin-bottom: 50px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

    # Editor Expander
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
                else:
                    st.error("Please enter an activity name.")

except Exception as e:
    st.error(f"System Error: {e}")
