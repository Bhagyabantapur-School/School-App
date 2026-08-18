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
    valid_next_times = df_videos[(df_videos['Next Time'].astype(str).str.strip() != '') & (df_videos['Date'].astype(str).str.strip() != '')].copy()
    
    if not valid_next_times.empty:
        def parse_datetime(row):
            try:
                nxt = str(row['Next Time']).strip()
                if len(nxt) > 5:
                    # Handles the new format where date is stored with the time
                    return IST.localize(datetime.strptime(nxt, '%Y-%m-%d %H:%M'))
                else:
                    # Handles older formatting (HH:MM only)
                    dt_str = f"{str(row['Date']).strip()} {nxt}"
                    return IST.localize(datetime.strptime(dt_str, '%Y-%m-%d %H:%M'))
            except Exception:
                return datetime.min.replace(tzinfo=IST)
                
        valid_next_times['DateTimeObj'] = valid_next_times.apply(parse_datetime, axis=1)
        
        # Only retain the absolute latest log per account
        latest_per_account = valid_next_times.sort_values('DateTimeObj', ascending=False).drop_duplicates(subset=['Account'], keep='first')
        latest_per_account = latest_per_account.sort_values(by='DateTimeObj')
        
        html_content = ""
        for _, row in latest_per_account.iterrows():
            dt_obj = row['DateTimeObj']
            acc_name = str(row['Account']).strip()
            
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
        get_routine_log_data.clear() 
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
        get_routine_log_data.clear() 
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
    st.markdown("**1. Time & Date Settings**")
    
    c_ft, c_nt = st.columns(2)
    with c_ft: 
        st.markdown("🔻 **Finished Setup**")
        entry_ft_date = st.date_input("Finished Date", value=now.date(), key="ft_date")
        entry_ft_time = st.time_input("Finished Time", value="now", key="entry_ft")
    with c_nt: 
        st.markdown("🔜 **Next Setup**")
        entry_nt_date = st.date_input("Next Date", value=now.date(), key="nt_date")
        entry_nt_time = st.time_input("Next Time", value="now", key="entry_nt")

    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    st.markdown("**2. Account & Session Context**")
    
    available_sessions = []
    if not log_df.empty and 'Activity' in log_df.columns:
        historical = log_df[(log_df['Activity'].astype(str).str.upper() == 'AI VIDEOS') & (log_df['End_Time'] != 'RUNNING')]
        if not historical.empty and 'Sub_Activities' in historical.columns:
            hist_list = historical['Sub_Activities'].dropna().unique().tolist()
            available_sessions = sorted(list(set(hist_list)), key=lambda x: int(''.join(filter(str.isdigit, str(x))) or 0), reverse=True)
    
    if not available_sessions:
        available_sessions = ["-- No Finished Sessions --"]
    
    c_acc, c_sess = st.columns(2)
    with c_sess:
        selected_session = st.selectbox("Link to Session", available_sessions)
        final_session = "" if selected_session == "-- No Finished Sessions --" else selected_session

    unique_accounts = df_videos['Account'].astype(str).str.strip().dropna().unique().tolist() if not df_videos.empty and 'Account' in df_videos.columns else []
    unique_accounts = [acc for acc in unique_accounts if acc and acc != 'nan'] 
    
    with c_acc:
        selected_account = st.selectbox("Account", ["-- Select / Type New --"] + unique_accounts)
        custom_account = st.text_input("Or Type New Account Name") if selected_account == "-- Select / Type New --" else ""
        final_account = custom_account.strip() if selected_account == "-- Select / Type New --" else selected_account
        
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    st.markdown("**3. Multiple Projects Configuration**")
    
    # Initialize the project count in session state
    if 'proj_count' not in st.session_state:
        st.session_state.proj_count = 1

    dependent_projects = []
    if final_account and not df_videos.empty and 'Account' in df_videos.columns and 'Project' in df_videos.columns:
        dependent_projects = df_videos[df_videos['Account'].astype(str).str.strip() == final_account]['Project'].astype(str).str.strip().dropna().unique().tolist()
        dependent_projects = [p for p in dependent_projects if p and p != 'nan']

    projects_data = []
    for i in range(st.session_state.proj_count):
        st.markdown(f"**Project Row {i+1}**")
        c_proj, c_sl, c_vid = st.columns([2, 1, 1])
        
        with c_proj:
            selected_project = st.selectbox("Project Name", ["-- Select / Type New --"] + dependent_projects, key=f"proj_sel_{i}", label_visibility="collapsed")
            custom_project = st.text_input("New Project", key=f"proj_cust_{i}", placeholder="Type new...") if selected_project == "-- Select / Type New --" else ""
            final_project = custom_project.strip() if selected_project == "-- Select / Type New --" else selected_project
            
        with c_sl:
            default_sl_no = 0
            if final_project and not df_videos.empty and 'Project' in df_videos.columns and 'Sl.No. of last Video' in df_videos.columns:
                proj_data = df_videos[df_videos['Project'].astype(str).str.strip() == final_project]
                if not proj_data.empty:
                    max_sl = pd.to_numeric(proj_data['Sl.No. of last Video'], errors='coerce').max()
                    if pd.notna(max_sl):
                        default_sl_no = int(max_sl)
            sl_no = st.number_input("Last Sl.No.", min_value=0, value=default_sl_no, step=1, format="%02d", key=f"sl_{i}")
            
        with c_vid:
            vids_session = st.number_input("Session Videos", min_value=0, step=1, format="%02d", key=f"vid_{i}")
            
        projects_data.append({
            "Project": final_project,
            "Sl.No": sl_no,
            "Videos": vids_session
        })

    # Add button to create a new project row dynamically
    if st.button("➕ Add Another Project"):
        st.session_state.proj_count += 1
        st.rerun()

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    submitted = st.button("💾 Save All Data to AI Videos", use_container_width=True, type="primary")
    
    if submitted:
        if not final_account:
            st.error("⚠️ Please provide an Account name.")
        else:
            rows_to_append = []
            ft_str = entry_ft_time.strftime('%H:%M')
            nt_str = f"{entry_nt_date.strftime('%Y-%m-%d')} {entry_nt_time.strftime('%H:%M')}"
            
            for p in projects_data:
                if p["Project"]:  # Skips rows where the user didn't enter a project
                    sl_no_str = f"{p['Sl.No']:02d}"
                    vids_session_str = f"{p['Videos']:02d}"
                    
                    row_data = [
                        entry_ft_date.strftime('%Y-%m-%d'),
                        ft_str,
                        nt_str,
                        GS_FORMULA, 
                        final_account,
                        p["Project"],
                        sl_no_str,
                        vids_session_str,
                        final_session
                    ]
                    rows_to_append.append(row_data)
            
            if rows_to_append:
                conn = init_connection()
                sheet = conn.open("AI Videos").sheet1
                
                # Append all project rows simultaneously
                sheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
                get_ai_videos_data.clear() 
                
                # Reset project row counter back to 1
                st.session_state.proj_count = 1
                
                if final_session:
                    st.success(f"✅ {len(rows_to_append)} Video Record(s) for {final_session} Logged Successfully!")
                else:
                    st.success(f"✅ {len(rows_to_append)} Video Record(s) Logged Successfully!")
                    
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("⚠️ Please provide at least one valid Project name.")
