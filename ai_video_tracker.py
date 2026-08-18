import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

# --- Constants & Formulas ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'
IST = pytz.timezone('Asia/Kolkata')

st.set_page_config(page_title="AI Video Tracker", page_icon="🎬", layout="centered")

# ==========================================
# Database Connection & Helper Functions
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60, show_spinner="Fetching Video Data...")
def get_ai_videos_data():
    conn = init_connection()
    try:
        sheet = conn.open("AI Videos").sheet1
        data = sheet.get_all_values()
        if not data:
            return pd.DataFrame(columns=["Date", "Finished Time", "Next Time", "Time Gap", "Account", "Project", "Sl.No. of last Video", "Videos of the session"])
        
        headers = data[0]
        records = data[1:]
        return pd.DataFrame(records, columns=headers)
    except Exception as e:
        st.error(f"Error loading AI Videos sheet: {e}")
        return pd.DataFrame(columns=["Date", "Finished Time", "Next Time", "Time Gap", "Account", "Project", "Sl.No. of last Video", "Videos of the session"])

def get_routine_log_data():
    conn = init_connection()
    try:
        sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
        data = sheet.get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame(columns=data[0])
    except:
        return pd.DataFrame()

# ==========================================
# Main App Logic
# ==========================================
now = datetime.now(IST)
today_str = now.strftime('%Y-%m-%d')
current_time_str = now.strftime('%H:%M')

df_videos = get_ai_videos_data()

# --- TOP SECTION: Upcoming Schedules ---
st.markdown("### ⏰ Upcoming Accounts (Sorted by Next Time)")

if not df_videos.empty:
    # Filter for rows that actually have a 'Next Time' entry
    valid_next_times = df_videos[df_videos['Next Time'].str.strip() != ''].copy()
    
    if not valid_next_times.empty:
        # Convert Next Time to a comparable format for sorting
        def parse_time(time_str):
            try: return datetime.strptime(time_str.strip(), '%H:%M').time()
            except: return datetime.max.time()
            
        valid_next_times['TimeObj'] = valid_next_times['Next Time'].apply(parse_time)
        valid_next_times = valid_next_times.sort_values(by='TimeObj')
        
        # Display the upcoming schedules in a row of metric cards
        cols = st.columns(min(len(valid_next_times), 4)) # Show top 4
        for idx, (_, row) in enumerate(valid_next_times.head(4).iterrows()):
            with cols[idx]:
                st.markdown(f"""
                <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center; border-left: 5px solid #0068c9;">
                    <h5 style="margin:0; color:#333;">{row['Next Time']}</h5>
                    <p style="margin:0; font-size: 14px; color:#555;"><b>{row['Account']}</b></p>
                    <p style="margin:0; font-size: 12px; color:#888;">{row['Project']}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No upcoming generation times logged yet.")
else:
    st.info("No records found in AI Videos sheet.")

st.markdown("---")

# --- ACTIVITY LOGGER (Start/Finish Session) ---
st.markdown("### ⏱️ Session Tracker")
log_df = get_routine_log_data()

is_running = False
active_row_idx = None
if not log_df.empty:
    running_sessions = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Sub_Activities'] == 'AI VIDEO GENERATION')]
    if not running_sessions.empty:
        is_running = True
        active_row_idx = running_sessions.index[0] + 2 # +2 for header and 0-indexing

col_start, col_finish = st.columns(2)

with col_start:
    if st.button("▶️ Start Video Session", use_container_width=True, disabled=is_running, type="primary"):
        conn = init_connection()
        sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
        row_data = [
            today_str, current_time_str, "RUNNING", GS_FORMULA, 
            "WORK", "AI VIDEO GENERATION", "", "Generating AI Videos", 
            "YouTube Creator", "TRUE", "TRUE", "6"
        ]
        sheet.append_row(row_data, value_input_option="USER_ENTERED")
        st.toast("✅ Session Started!")
        time.sleep(1)
        st.rerun()

with col_finish:
    if st.button("🛑 Finish Active Session", use_container_width=True, disabled=not is_running):
        conn = init_connection()
        sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
        try:
            sheet.update(range_name=f"C{active_row_idx}:D{active_row_idx}", values=[[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")
        except TypeError:
            sheet.update(f"C{active_row_idx}:D{active_row_idx}", [[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")
        st.toast("✅ Session Finished and Logged!")
        time.sleep(1)
        st.rerun()

st.markdown("---")

# --- DATA ENTRY & VIEW TABS ---
tab_view, tab_entry = st.tabs(["📊 Session Data", "📝 New Data Entry"])

with tab_view:
    if not df_videos.empty:
        st.dataframe(df_videos, use_container_width=True, hide_index=True)
    else:
        st.write("No data available.")

with tab_entry:
    with st.form("ai_video_entry_form", clear_on_submit=True):
        st.markdown("**Log New Video Generation Pattern**")
        
        c_date, c_ft, c_nt = st.columns(3)
        with c_date: 
            entry_date = st.date_input("Date", value=now.date())
        with c_ft: 
            # Default to current time, user can edit
            entry_ft = st.time_input("Finished Time", value=now.time())
        with c_nt: 
            entry_nt = st.time_input("Next Time", value=now.time())

        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
        
        # Extract unique accounts for dynamic dropdown
        unique_accounts = df_videos['Account'].str.strip().dropna().unique().tolist() if not df_videos.empty else []
        unique_accounts = [acc for acc in unique_accounts if acc] # Remove empty strings
        
        c_acc, c_proj = st.columns(2)
        with c_acc:
            selected_account = st.selectbox("Account", ["-- Select / Type New --"] + unique_accounts)
            custom_account = st.text_input("Or Type New Account Name") if selected_account == "-- Select / Type New --" else ""
            final_account = custom_account.strip() if selected_account == "-- Select / Type New --" else selected_account
            
        with c_proj:
            # Filter projects based on selected account
            dependent_projects = []
            if final_account and not df_videos.empty:
                dependent_projects = df_videos[df_videos['Account'].str.strip() == final_account]['Project'].str.strip().dropna().unique().tolist()
                dependent_projects = [p for p in dependent_projects if p]
                
            selected_project = st.selectbox("Project", ["-- Select / Type New --"] + dependent_projects)
            custom_project = st.text_input("Or Type New Project Name") if selected_project == "-- Select / Type New --" else ""
            final_project = custom_project.strip() if selected_project == "-- Select / Type New --" else selected_project

        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

        c_sl, c_vid = st.columns(2)
        with c_sl:
            sl_no = st.number_input("Sl.No. of last Video", min_value=0, step=1)
        with c_vid:
            vids_session = st.number_input("Videos of the session", min_value=0, step=1)

        submitted = st.form_submit_button("💾 Save Data to AI Videos", use_container_width=True, type="primary")
        
        if submitted:
            if final_account and final_project:
                conn = init_connection()
                sheet = conn.open("AI Videos").sheet1
                
                # Format times to HH:MM strings
                ft_str = entry_ft.strftime('%H:%M')
                nt_str = entry_nt.strftime('%H:%M')
                
                row_data = [
                    entry_date.strftime('%Y-%m-%d'),
                    ft_str,
                    nt_str,
                    GS_FORMULA, # Time Gap formula
                    final_account,
                    final_project,
                    sl_no,
                    vids_session
                ]
                
                sheet.append_row(row_data, value_input_option="USER_ENTERED")
                get_ai_videos_data.clear() # Clear cache to refresh the view
                st.success("✅ Video Data Logged Successfully!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("⚠️ Please provide both an Account and a Project name.")
