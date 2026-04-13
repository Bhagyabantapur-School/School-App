import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty Prep Tracker", page_icon="🗳️", layout="centered")

st.title("🗳️ Election Duty Log")
st.markdown("Track your daily practice and study sessions.")

# --- Google Sheets Authentication ---
# Ensure your service account JSON is securely stored in .streamlit/secrets.toml
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gsheets_client():
    # Pulls credentials from the Streamlit secrets dictionary
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=SCOPES
    )
    return gspread.authorize(creds)

try:
    client = get_gsheets_client()
    # Opens the spreadsheet and specifically targets the correct tab
    sheet = client.open("Election_Duty_Log").worksheet("Election_Duty_Log")
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Check your service account credentials. Error: {e}")
    st.stop()

# --- Logging Form ---
with st.form("duty_log_form"):
    st.subheader("New Session Entry")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        log_date = st.date_input("Date", date.today())
    with col2:
        start_time = st.time_input("Start Time")
    with col3:
        end_time = st.time_input("End Time")
        
    activity = st.selectbox(
        "Activity Type", 
        [
            "PPT Study (Bengali Rules)", 
            "Form 12/12A Practice", 
            "Hands-on Training Review",
            "EVM/VVPAT Mock Practice",
            "Marked Copy / Voter Roll Review",
            "Other"
        ]
    )
    
    notes = st.text_area("Notes / Key Learnings", placeholder="What did you focus on today?")
    
    submitted = st.form_submit_button("Log Activity to Sheet")

# --- Form Submission Logic ---
if submitted:
    # 1. Calculate Duration automatically
    start_dt = datetime.combine(log_date, start_time)
    end_dt = datetime.combine(log_date, end_time)
    
    # Handle cases where the session goes past midnight
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
        
    duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
    
    # 2. Format the row data exactly matching your headers
    # [Date, Start Time, End Time, Activity Type, Duration, Notes / Key Learnings]
    row_data = [
        log_date.strftime("%d-%m-%Y"),
        start_time.strftime("%I:%M %p"),
        end_time.strftime("%I:%M %p"),
        activity,
        f"{duration_minutes} mins",
        notes
    ]
    
    # 3. Append to the Google Sheet
    with st.spinner("Saving to Google Sheets..."):
        try:
            sheet.append_row(row_data)
            st.success(f"✅ Successfully logged {duration_minutes} minutes of {activity}!")
        except Exception as e:
            st.error(f"An error occurred while saving the data: {e}")
