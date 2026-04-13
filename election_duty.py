import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty Prep Tracker", page_icon="🗳️", layout="centered")

st.title("🗳️ Election Duty Tracker")
st.markdown("Schedule, log, and track your training progress.")

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

# --- Data Fetching Logic ---
@st.cache_data(ttl=60) 
def fetch_all_records():
    try:
        return sheet.get_all_records()
    except Exception:
        return []

records = fetch_all_records()

# Find rows where Start Time is "Pending". 
# Note: get_all_records() skips the header row (Row 1), so index 0 = Sheet Row 2
pending_sessions = []
for index, rec in enumerate(records):
    if rec.get("Start Time") == "Pending":
        pending_sessions.append({
            "sheet_row": index + 2, # Calculate exact Google Sheet row number
            "data": rec
        })

# --- App Layout: Tabs ---
tab1, tab2, tab3 = st.tabs(["📝 Log & Complete", "📅 Schedule Future", "📊 View Logs"])

# === TAB 1: LOG & COMPLETE ===
with tab1:
    action_type = st.radio("What would you like to do?", ["Complete a Scheduled Session", "Log a Brand New Session"], horizontal=True)
    st.divider()

    # --- OPTION A: Complete Scheduled ---
    if action_type == "Complete a Scheduled Session":
        if not pending_sessions:
            st.info("No pending scheduled sessions found. You can schedule one in the 'Schedule Future' tab!")
        else:
            # Create a dictionary for the dropdown menu
            options = {f"{s['data']['Date']} - {s['data']['Activity Type']}": s for s in pending_sessions}
            selected_str = st.selectbox("📌 Select Pending Session", list(options.keys()))
            selected_session = options[selected_str]
            
            st.write(f"**Original Notes:** {selected_session['data']['Notes / Key Learnings']}")
            
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.time_input("Start Time", step=60)
            with col2:
                end_time = st.time_input("End Time", step=60)
                
            # Pre-fill the text area with old notes so you can add to them
            updated_notes = st.text_area("Update Notes / Key Learnings", value=selected_session['data']['Notes / Key Learnings'])
            
            if st.button("✅ Complete Session", type="primary"):
                # Convert the stored date string back to a date object for math
                log_date = datetime.strptime(selected_session['data']['Date'], "%d-%m-%Y").date()
                
                start_dt = datetime.combine(log_date, start_time)
                end_dt = datetime.combine(log_date, end_time)
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                    
                total_minutes = int((end_dt - start_dt).total_seconds() / 60)
                duration_formatted = f"{total_minutes // 60:02d}h {total_minutes % 60:02d}m"
                
                row_num = selected_session['sheet_row']
                
                with st.spinner("Updating Google Sheet..."):
                    try:
                        # Update specific cells: Col 2(Start), Col 3(End), Col 5(Duration), Col 6(Notes)
                        sheet.update_cell(row_num, 2, start_time.strftime("%I:%M %p"))
                        sheet.update_cell(row_num, 3, end_time.strftime("%I:%M %p"))
                        sheet.update_cell(row_num, 5, duration_formatted)
                        sheet.update_cell(row_num, 6, updated_notes)
                        
                        st.success(f"Successfully completed the session: logged {duration_formatted}!")
                        st.cache_data.clear()
                        st.rerun() # Refresh the page to remove it from the pending list
                    except Exception as e:
                        st.error(f"Error updating sheet: {e}")

    # --- OPTION B: Log Brand New ---
    elif action_type == "Log a Brand New Session":
        col1, col2, col3 = st.columns(3)
        with col1:
            log_date = st.date_input("Date", date.today())
        with col2:
            start_time = st.time_input("Start Time", step=60)
        with col3:
            end_time = st.time_input("End Time", step=60)
            
        activity_selection = st.selectbox(
            "Activity Type", 
            ["PPT Study (Bengali Rules)", "Form 12/12A Practice", "Hands-on Training Review", "EVM/VVPAT Mock Practice", "Marked Copy / Voter Roll Review", "Other / Custom (Type below)"]
        )
        
        custom_activity = ""
        if activity_selection == "Other / Custom (Type below)":
            custom_activity = st.text_input("Custom Activity Type", placeholder="Type your new activity here...")
        
        notes = st.text_area("Notes / Key Learnings", placeholder="What did you focus on today?")
        
        if st.button("Log New Activity", type="primary"):
            if activity_selection == "Other / Custom (Type below)" and not custom_activity.strip():
                st.warning("⚠️ Please type a Custom Activity Type.")
            else:
                final_activity = custom_activity.strip() if activity_selection == "Other / Custom (Type below)" else activity_selection
                
                start_dt = datetime.combine(log_date, start_time)
                end_dt = datetime.combine(log_date, end_time)
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                    
                total_minutes = int((end_dt - start_dt).total_seconds() / 60)
                duration_formatted = f"{total_minutes // 60:02d}h {total_minutes % 60:02d}m"
                
                row_data = [
                    log_date.strftime("%d-%m-%Y"), start_time.strftime("%I:%M %p"), end_time.strftime("%I:%M %p"), 
                    final_activity, duration_formatted, notes
                ]
                
                with st.spinner("Saving to Google Sheets..."):
                    try:
                        sheet.append_row(row_data)
                        st.success(f"✅ Successfully logged {duration_formatted} of {final_activity}!")
                        st.cache_data.clear() 
                    except Exception as e:
                        st.error(f"Error saving: {e}")

# === TAB 2: SCHEDULE FUTURE ===
with tab2:
    st.subheader("📅 Schedule an Upcoming Training")
    
    # Default to tomorrow's date
    future_date = st.date_input("Scheduled Date", date.today() + timedelta(days=1))
    
    sched_activity_selection = st.selectbox(
        "Scheduled Activity Type", 
        ["Hands-on Training Review", "PPT Study (Bengali Rules)", "Form 12/12A Practice", "EVM/VVPAT Mock Practice", "Marked Copy / Voter Roll Review", "Other / Custom (Type below)"],
        key="sched_act"
    )
    
    sched_custom_activity = ""
    if sched_activity_selection == "Other / Custom (Type below)":
        sched_custom_activity = st.text_input("Custom Activity Type", placeholder="Type your scheduled activity here...", key="sched_cust")
        
    sched_notes = st.text_area("Initial Notes / Prep Required", placeholder="What do you need to prepare for this?")
    
    if st.button("Save Schedule", type="primary"):
        if sched_activity_selection == "Other / Custom (Type below)" and not sched_custom_activity.strip():
            st.warning("⚠️ Please type a Custom Activity Type.")
        else:
            final_sched_activity = sched_custom_activity.strip() if sched_activity_selection == "Other / Custom (Type below)" else sched_activity_selection
            
            # Use "Pending" for times and duration
            row_data = [
                future_date.strftime("%d-%m-%Y"),
                "Pending",
                "Pending",
                final_sched_activity,
                "Pending",
                sched_notes
            ]
            
            with st.spinner("Scheduling..."):
                try:
                    sheet.append_row(row_data)
                    st.success(f"✅ Scheduled **{final_sched_activity}** for {future_date.strftime('%d-%m-%Y')}!")
                    st.cache_data.clear() 
                except Exception as e:
                    st.error(f"Error scheduling: {e}")

# === TAB 3: VIEW LOGS ===
with tab3:
    st.subheader("Your Study History")
    
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

    df = pd.DataFrame(records)

    if not df.empty:
        # Optional: Clean up old "mins" data for display
        def clean_old_durations(val):
            if isinstance(val, str) and 'mins' in val:
                try:
                    total_mins = int(val.replace(' mins', '').strip())
                    return f"{total_mins // 60:02d}h {total_mins % 60:02d}m"
                except:
                    return val
            return val
            
        if 'Duration' in df.columns:
            df['Duration'] = df['Duration'].apply(clean_old_durations)

        # Apply a subtle highlight to Pending rows using Pandas Styler
        def highlight_pending(row):
            if row.get('Start Time') == 'Pending':
                return ['background-color: #ffcccc; color: black'] * len(row)
            return [''] * len(row)

        styled_df = df.style.apply(highlight_pending, axis=1)

        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        st.caption(f"Total entries logged: {len(df)}")
    else:
        st.info("No logs found yet.")
