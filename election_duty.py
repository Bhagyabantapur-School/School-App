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
    st.subheader("New Session Entry")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        log_date = st.date_input("Date", date.today())
    with col2:
        start_time = st.time_input("Start Time", step=60)
    with col3:
        end_time = st.time_input("End Time", step=60)
        
    activity_selection = st.selectbox(
        "Activity Type", 
        [
            "PPT Study (Bengali Rules)", 
            "Form 12/12A Practice", 
            "Hands-on Training Review",
            "EVM/VVPAT Mock Practice",
            "Marked Copy / Voter Roll Review",
            "Other / Custom (Type below)"
        ]
    )
    
    custom_activity = ""
    
    if activity_selection == "Other / Custom (Type below)":
        custom_activity = st.text_input("Custom Activity Type", placeholder="Type your new activity here...")
    
    notes = st.text_area("Notes / Key Learnings", placeholder="What did you focus on today?")
    
    if st.button("Log Activity to Sheet", type="primary"):
        
        if activity_selection == "Other / Custom (Type below)" and not custom_activity.strip():
            st.warning("⚠️ Please type a Custom Activity Type before submitting.")
        else:
            final_activity = custom_activity.strip() if activity_selection == "Other / Custom (Type below)" else activity_selection
            
            start_dt = datetime.combine(log_date, start_time)
            end_dt = datetime.combine(log_date, end_time)
            
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
                
            # --- UPDATED DURATION CALCULATION ---
            total_minutes = int((end_dt - start_dt).total_seconds() / 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            
            # Format as 00h 00m (the :02d ensures it always has two digits, like 01h 05m)
            duration_formatted = f"{hours:02d}h {minutes:02d}m"
            
            row_data = [
                log_date.strftime("%d-%m-%Y"),
                start_time.strftime("%I:%M %p"),
                end_time.strftime("%I:%M %p"),
                final_activity, 
                duration_formatted, # Using the new formatted string here
                notes
            ]
            
            with st.spinner("Saving to Google Sheets..."):
                try:
                    sheet.append_row(row_data)
                    # Updated success message to show the new format
                    st.success(f"✅ Successfully logged {duration_formatted} of **{final_activity}**!")
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
        # --- NEW CLEANUP LOGIC ---
        # Look for old entries ending in "mins" and convert them for display
        def clean_old_durations(val):
            if isinstance(val, str) and 'mins' in val:
                try:
                    total_mins = int(val.replace(' mins', '').strip())
                    h = total_mins // 60
                    m = total_mins % 60
                    return f"{h:02d}h {m:02d}m"
                except:
                    return val
            return val
            
        # Apply the cleaner function to the Duration column
        if 'Duration' in df.columns:
            df['Duration'] = df['Duration'].apply(clean_old_durations)
        # -------------------------

        st.dataframe(
            df, 
            use_container_width=True,
            hide_index=True
        )
        st.caption(f"Total entries logged: {len(df)}")
