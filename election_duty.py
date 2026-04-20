import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta, time

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty App - Party 116", page_icon="🗳️", layout="centered")

st.title("🗳️ Election Duty: Party 116")
st.markdown("Schedule, log, manage your team, and track Polling Day.")

# --- Google Sheets Authentication ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gsheets_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=SCOPES
    )
    return gspread.authorize(creds)

try:
    client = get_gsheets_client()
    spreadsheet = client.open("Election_Duty_Log")
    sheet_log = spreadsheet.worksheet("Election_Duty_Log")
    sheet_team = spreadsheet.worksheet("Team_Data")
    sheet_calls = spreadsheet.worksheet("Call_Logs")
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Error: {e}")
    st.stop()

# --- Data Fetching Logic ---
@st.cache_data(ttl=60) 
def fetch_logs():
    try: return sheet_log.get_all_records()
    except: return []

@st.cache_data(ttl=60)
def fetch_team():
    try: return sheet_team.get_all_records()
    except: return []

records = fetch_logs()
team_records = fetch_team()

pending_sessions = [{"sheet_row": i + 2, "data": r} for i, r in enumerate(records) if r.get("Start Time") == "Pending"]
team_list = [{"sheet_row": i + 2, "data": r} for i, r in enumerate(team_records)]

# --- App Layout: Tabs ---
# ADDED TAB 6 for the Timeline
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📝 Log Session", 
    "📅 Schedule", 
    "👥 Team", 
    "📊 Logs",
    "📖 1st PO Guide",
    "⏳ Poll Timeline" # NEW TAB
])

# === TABS 1 to 5 (Unchanged from previous version) ===
with tab1:
    action_type = st.radio("What would you like to do?", ["Complete a Scheduled Session", "Log a Brand New Session"], horizontal=True)
    st.divider()
    # ... (Keep all your existing Tab 1 code here) ...
    st.info("*(Tab 1 code remains the same as your previous version)*")

with tab2:
    st.subheader("📅 Schedule an Upcoming Training")
    # ... (Keep all your existing Tab 2 code here) ...

with tab3:
    st.subheader("👥 Polling Team Directory")
    # ... (Keep all your existing Tab 3 code here) ...

with tab4:
    st.subheader("Your Study History")
    # ... (Keep all your existing Tab 4 code here) ...

with tab5:
    st.header("📖 1st Polling Officer Guide")
    # ... (Keep all your existing Tab 5 code here) ...

# === TAB 6: DAY OF POLL TIMELINE (NEW) ===
with tab6:
    st.header("⏳ Election Day Timeline")
    st.markdown("Your minute-by-minute statutory schedule.")
    
    # Simulation Slider so you can test the color changes before the actual day!
    st.caption("🔧 **Testing Mode:** Drag the slider to simulate the time of day.")
    simulated_hour = st.slider("Simulate Time (24H Format)", min_value=4, max_value=20, value=7, step=1)
    
    st.divider()

    # Define the statutory ECI Timeline events
    timeline_events = [
        {"time": "05:00 AM", "hour": 5, "title": "Wake Up & Team Prep", "desc": "Ensure all team members are awake. Presiding Officer links EVM components (BU -> VVPAT -> CU). Do NOT switch on CU yet."},
        {"time": "05:30 AM", "hour": 5.5, "title": "Mock Poll Preparation", "desc": "Agents should arrive. Demonstrate empty EVM and empty VVPAT drop box. Switch on CU."},
        {"time": "05:45 AM", "hour": 5.75, "title": "Conduct Mock Poll", "desc": "Cast at least 50 votes across all candidates (including NOTA). Ensure agents participate."},
        {"time": "06:15 AM", "hour": 6.25, "title": "Clear Mock Poll & Seal EVM", "desc": "CRITICAL: Press CLOSE, RESULT, then CLEAR on CU. Remove Mock VVPAT slips, stamp them 'Mock Poll', and seal in black envelope. Seal the EVM with Green Paper Seal, Special Tag, and Address Tags."},
        {"time": "07:00 AM", "hour": 7, "title": "🟢 ACTUAL POLL COMMENCES", "desc": "Start allowing voters. 1st PO begins identifying voters and marking the Electoral Roll."},
        {"time": "09:00 AM", "hour": 9, "title": "1st 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 9 AM SMS report."},
        {"time": "11:00 AM", "hour": 11, "title": "2nd 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 11 AM SMS report."},
        {"time": "01:00 PM", "hour": 13, "title": "3rd 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 1 PM SMS report. (Take lunch in shifts)."},
        {"time": "03:00 PM", "hour": 15, "title": "4th 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 3 PM SMS report."},
        {"time": "05:00 PM", "hour": 17, "title": "5th 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 5 PM SMS report. Check queue outside."},
        {"time": "06:00 PM", "hour": 18, "title": "Distribute Queue Slips", "desc": "Distribute signed slips to all voters standing in the queue at exactly 6 PM, starting from the LAST person."},
        {"time": "06:30 PM", "hour": 18.5, "title": "🔴 CLOSE THE POLL", "desc": "After last voter, remove cap and press CLOSE button on CU. Switch off CU. Disconnect cables."},
        {"time": "07:00 PM", "hour": 19, "title": "Final Sealing & Forms", "desc": "Pack CU, BU, and VVPAT in carrying cases and seal with Address Tags. Complete Form 17C (Part 1) and Presiding Officer's Diary."},
    ]

    # Display the timeline
    for i, event in enumerate(timeline_events):
        # Determine the "Active" status by checking if the simulated time is right now
        is_active = False
        
        # Logic to find the current active task block
        if i < len(timeline_events) - 1:
            next_hour = timeline_events[i+1]["hour"]
            if event["hour"] <= simulated_hour < next_hour:
                is_active = True
        else:
            if simulated_hour >= event["hour"]:
                is_active = True

        # Apply CSS styling based on active status
        if is_active:
            st.success(f"### 👉 CURRENT TASK: {event['time']} - {event['title']}")
            st.write(f"**Action Required:** {event['desc']}")
        else:
            with st.expander(f"{event['time']} - {event['title']}"):
                st.write(event['desc'])
