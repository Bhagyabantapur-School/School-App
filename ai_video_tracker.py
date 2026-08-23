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

@st.cache_data(ttl=300, show_spinner="Fetching Data...")
def get_all_data():
    conn = init_connection()
    try:
        ss = conn.open("AI Videos")
        
        # 1. Get Video Patterns (Sheet1)
        try:
            sheet1 = ss.worksheet("Sheet1")
        except:
            sheet1 = ss.sheet1
            
        data1 = sheet1.get_all_values()
        if data1: data1[0] = [str(x).strip() for x in data1[0]] 
        
        cols1 = ["Date", "Finished Time", "Next Time", "Time Gap", "Account", "Project", "Sl.No. of last Video", "Videos of the session", "Session"]
        if len(data1) > 1:
            df_videos = pd.DataFrame(data1[1:], columns=data1[0])
            for col in cols1:
                if col not in df_videos.columns: df_videos[col] = ""
        else:
            df_videos = pd.DataFrame(columns=cols1)

        # 2. Get Sessions Tab (Local AI Videos Tracker)
        try:
            ws_sessions = ss.worksheet("Sessions")
        except gspread.exceptions.WorksheetNotFound:
            ws_sessions = ss.add_worksheet(title="Sessions", rows="1000", cols="10")
            ws_sessions.append_row(["Date", "Start_Time", "End_Time", "Duration", "Session_Name"])
        
        data2 = ws_sessions.get_all_values()
        if data2: data2[0] = [str(x).strip() for x in data2[0]]
        
        cols2 = ["Date", "Start_Time", "End_Time", "Duration", "Session_Name"]
        if len(data2) > 1:
            df_sessions = pd.DataFrame(data2[1:], columns=data2[0])
            for col in cols2:
                if col not in df_sessions.columns: df_sessions[col] = ""
        else:
            df_sessions = pd.DataFrame(columns=cols2)

        # 3. Get Routine Log (Fallback for old sessions)
        try:
            routine_sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
            data3 = routine_sheet.get_all_values()
            if data3: data3[0] = [str(x).strip() for x in data3[0]]
            df_routine = pd.DataFrame(data3[1:], columns=data3[0]) if len(data3) > 1 else pd.DataFrame()
        except:
            df_routine = pd.DataFrame()

        return df_videos, df_sessions, df_routine, False
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), str(e)

# ==========================================
# Main App Logic
# ==========================================
now = datetime.now(IST)
today_str = now.strftime('%Y-%m-%d')
current_time_str = now.strftime('%H:%M')

df_videos, df_sessions, df_routine, api_error = get_all_data()

# --- FAIL-SAFE TRIGGER ---
if api_error:
    st.error("⚠️ **Google Sheets API Limit Reached!**")
    st.write(f"Error Details: {api_error}")
    st.info("**Solution:** Please wait about 60 seconds, then click the button below to retry.")
    
    if st.button("🔄 Retry Connection", type="primary"):
        get_all_data.clear()
        st.rerun()
    st.stop()

# --- TOP SECTION: Upcoming Accounts ---
st.markdown("### ⏰ Upcoming Accounts")

if not df_videos.empty and 'Next Time' in df_videos.columns and 'Date' in df_videos.columns:
    valid_next_times = df_videos[(df_videos['Next Time'].astype(str).str.strip() != '') & (df_videos['Date'].astype(str).str.strip() != '')].copy()
    
    if not valid_next_times.empty:
        def parse_datetime(row):
            try:
                nxt = str(row['Next Time']).strip()
                if len(nxt) > 5:
                    return IST.localize(datetime.strptime(nxt, '%Y-%m-%d %H:%M'))
                else:
                    dt_str = f"{str(row['Date']).strip()} {nxt}"
                    return IST.localize(datetime.strptime(dt_str, '%Y-%m-%d %H:%M'))
            except Exception:
                return datetime.min.replace(tzinfo=IST)
                
        valid_next_times['DateTimeObj'] = valid_next_times.apply(parse_datetime, axis=1)
        
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
active_row_idx_sessions = None
active_row_idx_routine = None
active_session_name = ""

def extract_num(text):
    nums = re.findall(r'\b\d+\b', str(text))
    return int(nums[0]) if nums else 0

all_sess_names = []
if not df_routine.empty and 'Activity' in df_routine.columns:
    ai_rout = df_routine[df_routine['Activity'].astype(str).str.upper() == 'AI VIDEOS']
    if not ai_rout.empty and 'Sub_Activities' in ai_rout.columns:
        all_sess_names.extend(ai_rout['Sub_Activities'].dropna().tolist())

if not df_sessions.empty and 'Session_Name' in df_sessions.columns:
    all_sess_names.extend(df_sessions['Session_Name'].dropna().tolist())

next_num = 1
if all_sess_names:
    nums = [extract_num(x) for x in all_sess_names]
    if nums: next_num = max(nums) + 1

if not df_sessions.empty and 'Session_Name' in df_sessions.columns:
    running_sessions = df_sessions[df_sessions['End_Time'] == 'RUNNING']
    if not running_sessions.empty:
        is_running = True
        active_row_idx_sessions = running_sessions.index[0] + 2 
        active_session_name = str(running_sessions.iloc[0]['Session_Name'])

if not df_routine.empty and 'Activity' in df_routine.columns:
    running_routine = df_routine[(df_routine['End_Time'] == 'RUNNING') & (df_routine['Activity'].astype(str).str.upper() == 'AI VIDEOS')]
    if not running_routine.empty:
        is_running = True
        active_row_idx_routine = running_routine.index[0] + 2 
        if not active_session_name: active_session_name = str(running_routine.iloc[0]['Sub_Activities'])

next_session_name = f"Session {next_num:03d}"

col_start, col_finish = st.columns(2)

with col_start:
    if st.button(f"▶️ Start {next_session_name}", use_container_width=True, disabled=is_running, type="primary"):
        try:
            conn = init_connection()
            
            routine_sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
            routine_row = [today_str, current_time_str, "RUNNING", GS_FORMULA, "AI Videos", next_session_name, "", "Generating AI Videos", "YouTube Creator", "TRUE", "TRUE", "6"]
            routine_sheet.append_row(routine_row, value_input_option="USER_ENTERED")
            
            videos_sheet = conn.open("AI Videos").worksheet("Sessions")
            session_row = [today_str, current_time_str, "RUNNING", GS_FORMULA, next_session_name]
            videos_sheet.append_row(session_row, value_input_option="USER_ENTERED")

            get_all_data.clear() 
            st.toast(f"✅ {next_session_name} Started!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ API Error while starting session: {e}")

with col_finish:
    btn_label = f"🛑 Finish {active_session_name}" if is_running else "🛑 Finish Active Session"
    if st.button(btn_label, use_container_width=True, disabled=not is_running):
        try:
            conn = init_connection()
            
            if active_row_idx_sessions:
                ws_sessions = conn.open("AI Videos").worksheet("Sessions")
                try: ws_sessions.update(range_name=f"C{active_row_idx_sessions}:D{active_row_idx_sessions}", values=[[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")
                except TypeError: ws_sessions.update(f"C{active_row_idx_sessions}:D{active_row_idx_sessions}", [[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")
            
            if active_row_idx_routine:
                ws_routine = conn.open("MY ROUTINE 2026").worksheet("activity_log")
                try: ws_routine.update(range_name=f"C{active_row_idx_routine}:D{active_row_idx_routine}", values=[[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")
                except TypeError: ws_routine.update(f"C{active_row_idx_routine}:D{active_row_idx_routine}", [[current_time_str, GS_FORMULA]], value_input_option="USER_ENTERED")

            get_all_data.clear() 
            st.toast(f"✅ {active_session_name} Finished and Logged!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ API Error while finishing session: {e}")

st.markdown("---")

# --- DATA ENTRY & VIEW TABS ---
tab_view, tab_summary, tab_entry = st.tabs(["📊 Session Data", "📅 Daily Summary", "📝 New Data Entry"])

with tab_view:
    if not df_videos.empty:
        st.dataframe(df_videos, use_container_width=True, hide_index=True)
    else:
        st.write("No data available.")

with tab_summary:
    st.markdown("### 📊 Generation Report")
    
    if not df_videos.empty and 'Date' in df_videos.columns:
        unique_dates = df_videos['Date'].dropna().astype(str).str.strip().unique().tolist()
        unique_dates = sorted([d for d in unique_dates if d and d != 'nan'], reverse=True)
        
        if not unique_dates:
            st.info("No dates with video logs found.")
        else:
            default_idx = unique_dates.index(today_str) if today_str in unique_dates else 0
            selected_date = st.selectbox("🗓️ Select Date", unique_dates, index=default_idx)
            
            day_vids = df_videos[df_videos['Date'].astype(str).str.strip() == selected_date]
            
            day_logs_sessions = pd.DataFrame()
            if not df_sessions.empty and 'Date' in df_sessions.columns:
                day_logs_sessions = df_sessions[df_sessions['Date'].astype(str).str.strip() == selected_date]
                
            day_logs_routine = pd.DataFrame()
            if not df_routine.empty and 'Date' in df_routine.columns:
                day_logs_routine = df_routine[(df_routine['Date'].astype(str).str.strip() == selected_date) & 
                                              (df_routine['Activity'].astype(str).str.upper() == 'AI VIDEOS')]
            
            sessions = day_vids['Session'].astype(str).str.strip().unique().tolist()
            
            total_day_vids = 0
            total_day_mins = 0
            
            for sess in sessions:
                sess_name = sess if (sess and sess != 'nan' and sess != '-- No Finished Sessions --') else "Unlinked Session"
                
                sess_vids_df = day_vids[day_vids['Session'].astype(str).str.strip() == sess]
                sess_vids_count = pd.to_numeric(sess_vids_df['Videos of the session'], errors='coerce').fillna(0).sum()
                total_day_vids += sess_vids_count
                
                time_str = "N/A"
                dur_str = "0:00"
                
                if sess_name != "Unlinked Session":
                    match_log = pd.DataFrame()
                    if not day_logs_sessions.empty:
                        match_log = day_logs_sessions[day_logs_sessions['Session_Name'].astype(str).str.strip() == sess_name]
                    
                    if match_log.empty and not day_logs_routine.empty:
                        match_log = day_logs_routine[day_logs_routine['Sub_Activities'].astype(str).str.strip() == sess_name]
                        
                    if not match_log.empty:
                        row = match_log.iloc[-1] 
                        time_str = f"{row.get('Start_Time', '??')} - {row.get('End_Time', '??')}"
                        dur_str = str(row.get('Duration', '0:00')).strip()
                        
                if dur_str != "RUNNING" and dur_str != "N/A" and ":" in dur_str:
                    try:
                        h, m = dur_str.split(":")
                        total_day_mins += int(h) * 60 + int(m)
                    except: pass
                    
                st.markdown(f"""
                <div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <b style='font-size: 16px;'>{sess_name}</b>
                        <span style='color: #0068c9; font-weight: bold; font-size: 15px;'>🎬 {int(sess_vids_count)} Videos</span>
                    </div>
                    <div style='font-size: 14px; color: #555; margin-top: 5px;'>
                        ⏱️ Time: {time_str} &nbsp;|&nbsp; ⏳ Duration: {dur_str}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
            
            tot_h, tot_m = divmod(total_day_mins, 60)
            tot_dur_str = f"{tot_h}h {tot_m}m" if tot_h > 0 else f"{tot_m}m"
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<div style='text-align: center; padding: 15px; background-color: #e3f2fd; border-radius: 8px;'><h3 style='margin:0; color: #0068c9;'>{tot_dur_str}</h3><p style='margin:0; font-size:14px; color:#555;'>Total Time Used</p></div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div style='text-align: center; padding: 15px; background-color: #ffebee; border-radius: 8px;'><h3 style='margin:0; color: #ff4b4b;'>{int(total_day_vids)}</h3><p style='margin:0; font-size:14px; color:#555;'>Total Videos Created</p></div>", unsafe_allow_html=True)

    else:
        st.info("No video data logged yet.")

with tab_entry:
    st.markdown("**1. Session Setup Time**")
    
    current_ist_time = now.time()
    
    c_ft_date, c_ft_time = st.columns(2)
    with c_ft_date: 
        entry_ft_date = st.date_input("Finished Date", value=now.date(), key="ft_date")
    with c_ft_time:
        entry_ft_time = st.time_input("Finished Time", value=current_ist_time, key="entry_ft")

    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    st.markdown("**2. Session Context**")
    
    available_sessions = []
    
    if not df_routine.empty and 'Activity' in df_routine.columns:
        hist_rout = df_routine[(df_routine['Activity'].astype(str).str.upper() == 'AI VIDEOS') & (df_routine['End_Time'] != 'RUNNING')]
        if not hist_rout.empty and 'Sub_Activities' in hist_rout.columns:
            available_sessions.extend(hist_rout['Sub_Activities'].dropna().unique().tolist())
            
    if not df_sessions.empty and 'Session_Name' in df_sessions.columns:
        hist_sess = df_sessions[df_sessions['End_Time'] != 'RUNNING']
        if not hist_sess.empty:
            available_sessions.extend(hist_sess['Session_Name'].dropna().unique().tolist())

    if available_sessions:
        available_sessions = sorted(list(set(available_sessions)), key=lambda x: int(''.join(filter(str.isdigit, str(x))) or 0), reverse=True)
    else:
        available_sessions = ["-- No Finished Sessions --"]
    
    selected_session = st.selectbox("Link to Session", available_sessions)
    final_session = "" if selected_session == "-- No Finished Sessions --" else selected_session

    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    st.markdown("**3. Accounts & Projects**")
    
    if 'account_blocks' not in st.session_state:
        st.session_state.account_blocks = [1] 

    unique_accounts = df_videos['Account'].astype(str).str.strip().dropna().unique().tolist() if not df_videos.empty and 'Account' in df_videos.columns else []
    unique_accounts = [acc for acc in unique_accounts if acc and acc != 'nan'] 

    projects_data = []

    for acc_idx, proj_count in enumerate(st.session_state.account_blocks):
        with st.container():
            st.markdown(f"<h5 style='color: #0068c9;'>👤 Account Block {acc_idx + 1}</h5>", unsafe_allow_html=True)
            
            c_acc, c_nt_date, c_nt_time = st.columns([2, 1, 1])
            with c_acc:
                selected_account = st.selectbox("Account", ["-- Select / Type New --"] + unique_accounts, key=f"acc_sel_{acc_idx}")
                custom_account = st.text_input("New Account Name", key=f"acc_cust_{acc_idx}") if selected_account == "-- Select / Type New --" else ""
                final_account = custom_account.strip() if selected_account == "-- Select / Type New --" else selected_account
            with c_nt_date:
                acc_nt_date = st.date_input("Next Date", value=now.date(), key=f"nt_date_{acc_idx}")
            with c_nt_time:
                acc_nt_time = st.time_input("Next Time", value=current_ist_time, key=f"nt_time_{acc_idx}")
            
            dependent_projects = []
            if final_account and not df_videos.empty and 'Account' in df_videos.columns and 'Project' in df_videos.columns:
                dependent_projects = df_videos[df_videos['Account'].astype(str).str.strip() == final_account]['Project'].astype(str).str.strip().dropna().unique().tolist()
                dependent_projects = [p for p in dependent_projects if p and p != 'nan']

            for proj_idx in range(proj_count):
                st.markdown(f"**Project {proj_idx + 1}**")
                c_proj, c_sl, c_vid = st.columns([2, 1, 1])
                
                with c_proj:
                    selected_project = st.selectbox("Project Name", ["-- Select / Type New --"] + dependent_projects, key=f"proj_sel_{acc_idx}_{proj_idx}", label_visibility="collapsed")
                    custom_project = st.text_input("New Project", key=f"proj_cust_{acc_idx}_{proj_idx}", placeholder="Type new...") if selected_project == "-- Select / Type New --" else ""
                    final_project = custom_project.strip() if selected_project == "-- Select / Type New --" else selected_project
                    
                dynamic_vid_key = f"vid_{acc_idx}_{proj_idx}_{final_project}"
                # Grab real-time user input for Session Videos
                current_vids = st.session_state.get(dynamic_vid_key, 0)
                
                historical_sl_no = 0
                if final_project and not df_videos.empty and 'Project' in df_videos.columns and 'Sl.No. of last Video' in df_videos.columns:
                    proj_data = df_videos[df_videos['Project'].astype(str).str.strip() == final_project]
                    if not proj_data.empty:
                        last_logged_val = proj_data.iloc[-1]['Sl.No. of last Video']
                        try:
                            historical_sl_no = int(last_logged_val)
                        except (ValueError, TypeError):
                            pass
                
                # Auto-increment calculation
                auto_sl_no = historical_sl_no + current_vids
                
                with c_sl:
                    dynamic_sl_key = f"sl_{acc_idx}_{proj_idx}_{final_project}"
                    sl_no = st.number_input("Last Sl.No.", min_value=0, value=auto_sl_no, step=1, format="%02d", key=dynamic_sl_key)
                    
                with c_vid:
                    vids_session = st.number_input("Session Videos", min_value=0, step=1, format="%02d", key=dynamic_vid_key)
                    
                projects_data.append({
                    "Account": final_account,
                    "Project": final_project,
                    "Sl.No": sl_no,
                    "Videos": vids_session,
                    "Next_Date": acc_nt_date,
                    "Next_Time": acc_nt_time
                })
            
            if st.button(f"➕ Add Project to Account {acc_idx + 1}", key=f"add_proj_{acc_idx}"):
                st.session_state.account_blocks[acc_idx] += 1
                st.rerun()
                
            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

    if st.button("➕ Add Another Account", type="secondary"):
        st.session_state.account_blocks.append(1)
        st.rerun()

    st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)
    submitted = st.button("💾 Save All Data to AI Videos", use_container_width=True, type="primary")
    
    if submitted:
        try:
            rows_to_append = []
            ft_str = entry_ft_time.strftime('%H:%M')
            
            for p in projects_data:
                if p["Account"] and p["Project"]:  
                    sl_no_str = f"{p['Sl.No']:02d}"
                    vids_session_str = f"{p['Videos']:02d}"
                    
                    nt_str = f"{p['Next_Date'].strftime('%Y-%m-%d')} {p['Next_Time'].strftime('%H:%M')}"
                    
                    row_data = [
                        entry_ft_date.strftime('%Y-%m-%d'),
                        ft_str,
                        nt_str,
                        GS_FORMULA, 
                        p["Account"],
                        p["Project"],
                        sl_no_str,
                        vids_session_str,
                        final_session
                    ]
                    rows_to_append.append(row_data)
            
            if rows_to_append:
                conn = init_connection()
                sheet = conn.open("AI Videos").sheet1
                sheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
                get_all_data.clear() 
                
                st.session_state.account_blocks = [1]
                
                if final_session:
                    st.success(f"✅ {len(rows_to_append)} Record(s) for {final_session} Logged Successfully!")
                else:
                    st.success(f"✅ {len(rows_to_append)} Record(s) Logged Successfully!")
                    
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("⚠️ Please fill out at least one valid Account and Project combination.")
        except Exception as e:
            st.error(f"⚠️ API Error while saving data: {e}")
