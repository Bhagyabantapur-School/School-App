import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty Prep Tracker", page_icon="🗳️", layout="centered")

st.title("🗳️ Election Duty Tracker")
st.markdown("Log your sessions and track your training progress.")

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
    sheet = client.open("Election_Duty_Log").worksheet("Election_Duty_Log")
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Error: {e}")
    st.stop()

# --- App Layout: Tabs ---
tab1, tab2 = st.tabs(["📝 Log Entry", "📊 View Logs"])

# === TAB 1: LOG ENTRY ===
with tab1:
    with st.form("duty_log_form"):
        st.subheader("New Session Entry")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            log_date = st.date_input("Date", date.today())
        with col2:
            start_time = st.time_input("Start Time")
        with col3:
            end_time = st.time_input("End Time")
            
        activity_selection = st.selectbox(
            "Activity Type", 
            [
                "PPT Study (Bengali Rules)", 
                "Form 12/12A Practice", 
                "Hands-on Training Review",
                "EVM/VVPAT Mock Practice",
                "Marked Copy / Voter Roll Review",
                "Other / Custom (Type below)" # Updated option
            ]
        )
        
        # New text input for custom activity
        custom_activity = st.text_input("Custom Activity Type", placeholder="Type new activity if 'Other' is selected above...")
        
        notes = st.text_area("Notes / Key Learnings", placeholder="What did you focus on today?")
        
        submitted = st.form_submit_button("Log Activity to Sheet")

    # Form Submission Logic
    if submitted:
        # Determine which activity name to use
        final_activity = custom_activity.strip() if activity_selection == "Other / Custom (Type below)" and custom_activity.strip() else activity_selection
        
        # Require text if "Other" was selected
        if activity_selection == "Other / Custom (Type below)" and not custom_activity.strip():
            st.warning("⚠️ Please type a Custom Activity Type before submitting.")
        else:
            start_dt = datetime.combine(log_date, start_time)
            end_dt = datetime.combine(log_date, end_time)
            
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
                
            duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
            
            row_data = [
                log_date.strftime("%d-%m-%Y"),
                start_time.strftime("%I:%M %p"),
                end_time.strftime("%I:%M %p"),
                final_activity, # Using the custom text if provided
                f"{duration_minutes} mins",
                notes
            ]
            
            with st.spinner("Saving to Google Sheets..."):
                try:
                    sheet.append_row(row_data)
                    st.success(f"✅ Successfully logged {duration_minutes} minutes of **{final_activity}**!")
                    st.cache_data.clear() 
                except Exception as e:
                    st.error(f"An error occurred while saving: {e}")


# === TAB 2: VIEW LOGS ===
with tab2:
    st.subheader("Your Study History")
    
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

    @st.cache_data(ttl=60) 
    def fetch_data():
        try:
            records = sheet.get_all_records()
            return pd.DataFrame(records)
        except Exception as e:
            st.error(f"Could not load data: {e}")
            return pd.DataFrame()

    df = fetch_data()

    if not df.empty:
        st.dataframe(
            df, 
            use_container_width=True,
            hide_index=True
        )
        st.caption(f"Total entries logged: {len(df)}")
    else:
        st.info("No logs found yet. Start by adding a new entry in the 'Log Entry' tab!")
