import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time
import re

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

@st.cache_data(ttl=300, show_spinner="Fetching Video Data...")
def get_ai_videos_data():
    conn = init_connection()
    try:
        sheet = conn.open("AI Videos").sheet1
        data = sheet.get_all_values()
        default_cols = ["Date", "Finished Time", "Next Time", "Time Gap", "Account", "Project", "Sl.No. of last Video", "Videos of the session", "Session"]
        if not data:
            return pd.DataFrame(columns=default_cols)
        
        headers = data[0]
        records = data[1:]
        return pd.DataFrame(records, columns=headers)
    except Exception as e:
        st.error(f"Error loading AI Videos sheet: {e}")
        return pd.DataFrame(columns=["Date", "Finished Time", "Next Time", "Time Gap", "Account", "Project", "Sl.No. of last Video", "Videos of the session", "Session"])

@st.cache_data(ttl=300, show_spinner="Fetching Routine Data...")
def get_routine_log_data():
    conn = init_connection()
    try:
        sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
        data = sheet.get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame(columns=data[0])
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# Main App Logic
# ==========================================
now = datetime.now(IST)
today_str = now.strftime('%Y-%m-%d')
current_time_str = now.strftime('%H:%M')

df_videos = get_ai_videos_data()
log_df = get_routine_log_data()

# --- TOP SECTION: Upcoming Accounts ---
st.markdown("### ⏰ Upcoming Accounts")

if not df_videos.empty and 'Next Time' in df_videos.columns and 'Date' in df_videos.columns:
    # Filter out empty dates/times
    valid_next_times = df_videos[(df_videos['Next Time'].astype(str).str.strip() != '') & (df_videos['Date'].astype(str).str.strip() != '')].copy()
    
    if not valid_next_times.empty:
        def parse_datetime(row):
            try:
                dt_str = f"{str(row['Date']).strip()} {str(row['Next Time']).strip()}"
                return IST.localize(datetime.strptime(dt_str, '%Y-%m-%d %H:%M'))
            except Exception:
                return datetime.min.replace(tzinfo=IST)
                
        # Create full datetime objects for accurate comparison
        valid_next_times['DateTimeObj'] = valid_next_times.apply(parse_datetime, axis=1)
        
        # 1. Filter so ONLY the absolute latest entry per account is retained
        latest_per_account = valid_next_times.sort_values('DateTimeObj', ascending=False).drop_duplicates(subset=['Account'], keep='first')
        
        # Sort chronologically for the display order
        latest_per_account = latest_per_account.sort_values(by='DateTimeObj')
        
        # 2. Compact Vertical UI
        html_content = ""
        for _, row in latest_per_account.iterrows():
            dt_obj = row['DateTimeObj']
            acc_name = str(row['Account']).strip()
            
            # Check if the time has been reached or passed
            if now >= dt_obj:
                html_content += f"""
                <div style='padding: 10px 15px; margin-bottom: 8px; background-color: #e8f5e9; border-left: 4px solid #4caf50; border-radius: 6px; color: #1b5e20; font-size: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
                    <b>{acc_name}</b> available now
                </div>
                """
            else:
                date_str = dt_obj.strftime('%b %d')
                time_str = dt_obj.strftime('%H:%M')
                html_content += f"""
                <div style='padding: 10px 15px; margin-bottom: 8px; background-color: #f8f9fa; border-left: 4px solid #0068c9; border-radius: 6px; color: #333; font-size: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
                    <b>{acc_name}</b> available on {date_str} at {time_str}
                </div>
                """
                
        st.markdown(html_content, unsafe_allow_html=True)
    else:
        st.info("No upcoming generation times logged yet.")
else:
    st.info("No records found in AI Videos sheet.")

st.markdown("---")

# --- ACTIVITY LOGGER (Start/Finish Session) ---
st.markdown("### ⏱️ Session Tracker")

is_running = False
active_row_idx = None

def extract_num(text):
    nums = re.findall(r'\b\d+\b', str(text))
    return int(nums[0]) if nums else 0

next_num = 1
active_session_name = ""

if not log_df.empty and 'Activity' in log_df.columns:
    ai_sessions_df = log_df[log_df['Activity'].astype(str).str.upper() == 'AI VIDEOS']
    
    if not ai_sessions_df.empty and 'Sub_Activities' in ai_sessions_df.columns:
        max_num = ai_sessions_df['Sub_Activities'].apply(extract_num).max()
        if pd.notna(max_num):
            next_num = int(max_num) + 1
            
        running_sessions = ai_sessions_df[ai_sessions_df['End_Time'] == 'RUNNING']
        if not running_sessions.empty:
            is_running = True
            active_row_idx = running_sessions.index[0] + 2 
            active_session_name = str(running_sessions.iloc[0]['Sub_Activities'])

next_session_name = f"Session {next_num:03d}"

col_start, col_finish = st.columns(2)

with col_start:
    if st.button(f"▶️ Start {next_session_name}", use_container_width=True, disabled=is_running, type="primary"):
        conn = init_connection()
        sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
        row_data = [
            today_str, current_time_str, "RUNNING", GS_FORMULA, 
            "AI Videos", next_session_name, "", "Generating AI Videos", 
            "YouTube Creator", "TRUE", "TRUE", "6"
        ]
        sheet.append_row(row_data, value_input_option="USER_ENTERED")
        get_routine_log_data.clear() # Clear cache to refresh state
        st.toast(f"✅ {next_session_name} Started!")
        time.sleep(1)
        st.rerun()

with col_finish:
    btn_label = f"🛑 Finish {active_session_name}" if is_running else "🛑 Finish Active Session"
    if st.button(btn_label, use_container_width=True, disabled=not is_running):
        conn = init_connection()
        sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
        try:
            sheet.update(range_name=f"C{active_row_idx}:D{active_row_idx}", values=[[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")
        except TypeError:
            sheet.update(f"C{active_row_idx}:D{active_row_idx}", [[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")
        get_routine_log_data.clear() # Clear cache to refresh state
        st.toast(f"✅ {active_session_name} Finished and Logged!")
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
    st.markdown("**Log New Video Generation Pattern**")
    
    c_date, c_ft, c_nt = st.columns(3)
    with c_date: 
        entry_date = st.date_input("Date", value=now.date())
    with c_ft: 
        entry_ft = st.time_input("Finished Time", value="now", key="entry_ft")
    with c_nt: 
        entry_nt = st.time_input("Next Time", value="now", key="entry_nt")

    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    
    available_sessions = []
    if not log_df.empty and 'Activity' in log_df.columns:
        historical = log_df[(log_df['Activity'].astype(str).str.upper() == 'AI VIDEOS') & (log_df['End_Time'] != 'RUNNING')]
        if not historical.empty and 'Sub_Activities' in historical.columns:
            hist_list = historical['Sub_Activities'].dropna().unique().tolist()
            available_sessions = sorted(list(set(hist_list)), key=lambda x: int(''.join(filter(str.isdigit, str(x))) or 0), reverse=True)
    
    if not available_sessions:
        available_sessions = ["-- No Finished Sessions --"]
    
    c_acc, c_proj, c_sess = st.columns(3)
    with c_sess:
        selected_session = st.selectbox("Link to Session", available_sessions)
        final_session = "" if selected_session == "-- No Finished Sessions --" else selected_session

    unique_accounts = df_videos['Account'].astype(str).str.strip().dropna().unique().tolist() if not df_videos.empty and 'Account' in df_videos.columns else []
    unique_accounts = [acc for acc in unique_accounts if acc and acc != 'nan'] 
    
    with c_acc:
        selected_account = st.selectbox("Account", ["-- Select / Type New --"] + unique_accounts)
        custom_account = st.text_input("Or Type New Account Name") if selected_account == "-- Select / Type New --" else ""
        final_account = custom_account.strip() if selected_account == "-- Select / Type New --" else selected_account
        
    with c_proj:
        dependent_projects = []
        if final_account and not df_videos.empty and 'Account' in df_videos.columns and 'Project' in df_videos.columns:
            dependent_projects = df_videos[df_videos['Account'].astype(str).str.strip() == final_account]['Project'].astype(str).str.strip().dropna().unique().tolist()
            dependent_projects = [p for p in dependent_projects if p and p != 'nan']
            
        selected_project = st.selectbox("Project", ["-- Select / Type New --"] + dependent_projects)
        custom_project = st.text_input("Or Type New Project Name") if selected_project == "-- Select / Type New --" else ""
        final_project = custom_project.strip() if selected_project == "-- Select / Type New --" else selected_project

    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

    # Calculate default Sl.No. based on the selected Project
    default_sl_no = 0
    if final_project and not df_videos.empty and 'Project' in df_videos.columns and 'Sl.No. of last Video' in df_videos.columns:
        proj_data = df_videos[df_videos['Project'].astype(str).str.strip() == final_project]
        if not proj_data.empty:
            max_sl = pd.to_numeric(proj_data['Sl.No. of last Video'], errors='coerce').max()
            if pd.notna(max_sl):
                default_sl_no = int(max_sl)

    c_sl, c_vid = st.columns(2)
    with c_sl:
        sl_no = st.number_input("Sl.No. of last Video", min_value=0, value=default_sl_no, step=1, format="%02d")
    with c_vid:
        vids_session = st.number_input("Videos of the session", min_value=0, step=1, format="%02d")

    submitted = st.button("💾 Save Data to AI Videos", use_container_width=True, type="primary")
    
    if submitted:
        if final_account and final_project:
            conn = init_connection()
            sheet = conn.open("AI Videos").sheet1
            
            ft_str = entry_ft.strftime('%H:%M')
            nt_str = entry_nt.strftime('%H:%M')
            
            sl_no_str = f"{sl_no:02d}"
            vids_session_str = f"{vids_session:02d}"
            
            row_data = [
                entry_date.strftime('%Y-%m-%d'),
                ft_str,
                nt_str,
                GS_FORMULA, 
                final_account,
                final_project,
                sl_no_str,
                vids_session_str,
                final_session
            ]
            
            sheet.append_row(row_data, value_input_option="USER_ENTERED")
            get_ai_videos_data.clear() 
            
            if final_session:
                st.success(f"✅ Video Data for {final_session} Logged Successfully!")
            else:
                st.success("✅ Video Data Logged Successfully!")
                
            time.sleep(1)
            st.rerun()
        else:
            st.error("⚠️ Please provide both an Account and a Project name.")
