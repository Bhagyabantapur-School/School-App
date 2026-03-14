import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# 1. Mobile-First Configuration
st.set_page_config(page_title="Live Routine", page_icon="⏱️", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    </style>
""", unsafe_allow_html=True)

# 2. Database Connection (CRITICAL: Scopes updated for write access)
@st.cache_resource
def init_connection():
    # Removed '.readonly' to allow the Editor permissions to function
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

# Helper function to get the raw sheet object for writing
def get_sheet():
    client = init_connection()
    return client.open("MY ROUTINE 2026").sheet1

# 3. Data Processing
@st.cache_data(ttl=60) 
def get_routine_data():
    sheet = get_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

try:
    df = get_routine_data()
    
    # 4. Live Time Tracking
    now = datetime.now()
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
                    current_activity = str(row['Activity']).strip()
                    break
            except ValueError:
                continue

    # 5. Dynamic UI Coloring
    if current_activity in ["SUBORNO CARE", "BRING SUBORNO"]:
        color = "#ff4b4b" 
    elif current_activity == "WORK":
        color = "#0068c9" 
    elif current_activity == "HEALTH":
        color = "#2e7b32" 
    else:
        color = "#333333"

    st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 30px; margin-bottom: 50px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

    # 6. Update Form (Mobile Editor)
    with st.expander("✏️ Quick Add / Edit Routine"):
        with st.form("edit_routine_form", clear_on_submit=True):
            st.markdown("### Add New Time Slot")
            
            col1, col2 = st.columns(2)
            with col1:
                input_day = st.selectbox("Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], index=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(current_day))
            with col2:
                input_activity = st.text_input("Activity (e.g., WORK, HEALTH)")
            
            col3, col4 = st.columns(2)
            with col3:
                input_start = st.time_input("Start Time")
            with col4:
                input_end = st.time_input("End Time")
                
            submitted = st.form_submit_button("Update Sheet", use_container_width=True)
            
            if submitted:
                if input_activity:
                    # Format times to match your existing sheet structure (HH:MM)
                    start_str = input_start.strftime('%H:%M')
                    end_str = input_end.strftime('%H:%M')
                    
                    # Calculate duration automatically
                    start_dt = datetime.combine(datetime.today(), input_start)
                    end_dt = datetime.combine(datetime.today(), input_end)
                    if end_dt < start_dt:
                        # Handle overnight slots
                        end_dt = end_dt.replace(day=end_dt.day + 1)
                    duration_td = end_dt - start_dt
                    hours, remainder = divmod(duration_td.seconds, 3600)
                    minutes = remainder // 60
                    duration_str = f"{hours}:{minutes:02d}"

                    # Append to Google Sheet (Day, Start_Time, End_Time, Duration, Activity)
                    sheet = get_sheet()
                    sheet.append_row([input_day, start_str, end_str, duration_str, input_activity.upper()])
                    
                    # Clear the cache so the app pulls the fresh data immediately
                    st.cache_data.clear()
                    st.success(f"Added {input_activity} to {input_day}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please enter an activity name.")

    # 7. Auto-Refresh Loop (Only runs if the expander is closed to prevent form interruption)
    time.sleep(60)
    st.rerun()

except Exception as e:
    st.error(f"Error: {e}")