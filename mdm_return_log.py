import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

# --- Master Google Sheets Formulas for Duration ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'
MDM_GS_FORMULA = '=IF(INDIRECT("E"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("E"&ROW())-INDIRECT("D"&ROW()), 1), "h:mm"), ""))'

# ==========================================
# 1. Configuration & Session State Init
# ==========================================
st.set_page_config(page_title="MDM Return Logger", page_icon="📦", layout="wide")

# --- BACK BUTTON (PRESERVED IN STRICT LOCATION) ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("dashboard.py")
st.write("---") 
# --------------------------------------------------

if 'pomodoro_state' not in st.session_state:
    st.session_state.pomodoro_state = {}

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 3rem; padding-bottom: 2rem;}
    
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 0px !important;
        border: 1px solid #cccccc !important;
        background-color: #ffffff !important;
        box-shadow: none !important;
    }
    
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.9; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.9; }
    }
    
    @media (max-width: 640px) {
        .stHeadingContainer h1 {
            font-size: 1.8rem !important;
        }
        div.stButton > button {
            margin-top: 5px;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Database Connection & Caching Helpers
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource
def get_main_spreadsheet():
    client = init_connection()
    return client.open("MY ROUTINE 2026")

@st.cache_resource
def get_mdm_spreadsheet():
    client = init_connection()
    return client.open("MDM RETURN LOG")

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try:
        sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
    except TypeError:
        sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=300)
def get_activity_log():
    ss = get_main_spreadsheet()
    sheet = ss.worksheet("activity_log")
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    return df

@st.cache_data(ttl=300)
def fetch_mdm_raw_data():
    try:
        ss = get_mdm_spreadsheet()
        config_data = ss.worksheet("CONFIG").get_all_records()
        log_data = ss.get_worksheet(0).get_all_values()
        data_tab_data = ss.worksheet("Data").get_all_records() # Fetches the new Data tab
        return config_data, log_data, data_tab_data
    except Exception as e:
        st.error(f"Failed to fetch MDM data: {e}")
        return [], [], []

# --- SAFEGUARD FUNCTION: Strips hidden spaces from Google Sheets headers and cells ---
def get_clean_val(row_dict, target_key):
    for k, v in row_dict.items():
        if str(k).strip().lower() == target_key.strip().lower():
            return str(v).strip()
    return ""

def get_mdm_tasks(config_data, log_data):
    if not config_data: return ["Error loading tasks"]
    all_tasks = []
    for row in config_data:
        sheet_val = get_clean_val(row, 'Sheet')
        work_val = get_clean_val(row, 'Work')
        status_val = get_clean_val(row, 'Status').upper()
        
        # Safe logic to hide already completed tasks
        if (sheet_val or work_val) and status_val != "COMPLETED": 
            all_tasks.append(f"{sheet_val} | {work_val}")
            
    if not all_tasks: return ["🎉 All MDM tasks completed!"]
    return all_tasks

# ==========================================
# 3. Main Application Logic
# ==========================================
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)
today_str = now.strftime('%Y-%m-%d')
mdm_date_str = now.strftime('%d-%b-%Y') 

try:
    log_df = get_activity_log()
    config_raw, log_raw, data_raw = fetch_mdm_raw_data()
    mdm_tasks_list = get_mdm_tasks(config_raw, log_raw)
    
    # --- EXTRACT DATA FROM THE NEW "Data" TAB ---
    app_title = "MDM RETURN PREPARE"
    app_year = now.strftime('%Y')
    default_month = now.strftime('%B')
    
    if data_raw and len(data_raw) > 0:
        app_title = get_clean_val(data_raw[0], 'Title') or app_title
        default_month = get_clean_val(data_raw[0], 'Month') or default_month
        app_year = get_clean_val(data_raw[0], 'Year') or app_year

    # Set the session state month ONLY on the first load using the Data tab
    if 'selected_month' not in st.session_state:
        st.session_state.selected_month = default_month

    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Notes'] == 'MDM Return Task')]
    active_count = len(running_tasks)

    # --- PROGRESS CALCULATION ---
    total_tasks = len(config_raw)
    completed_count = sum(1 for row in config_raw if get_clean_val(row, 'Status').upper() == "COMPLETED")
    progress_percentage = int((completed_count / total_tasks) * 100) if total_tasks > 0 else 0

    # --- HEADER & SYNC ---
    col_title, col_sync = st.columns([4, 1])
    with col_title:
        # Title updated dynamically from the Data tab
        st.markdown(f"<h1 style='margin-top: 0px;'>📦 {app_title} ({st.session_state.selected_month} {app_year})</h1>", unsafe_allow_html=True)
    with col_sync:
        if st.button("🔄 Sync", use_container_width=True):
            get_activity_log.clear(); fetch_mdm_raw_data.clear(); st.rerun()

    # --- PROGRESS BOX ---
    st.markdown("""<div id="progress_box_anchor"></div><style>div.element-container:has(#progress_box_anchor) + div[data-testid="stHorizontalBlock"] { background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%); border: 1px solid #7dd3fc; border-radius: 16px; padding: 15px 25px; align-items: center; margin-bottom: 25px; margin-top: 15px; }</style>""", unsafe_allow_html=True)
    col_text, col_chart = st.columns([1.5, 1])
    with col_text:
        st.markdown(f"<h3 style='margin: 0; color: #1e3a8a;'>Progress</h3><p style='color: #64748b;'>{completed_count} of {total_tasks} finished</p>", unsafe_allow_html=True)
    with col_chart:
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Pie(values=[progress_percentage, 100-progress_percentage], hole=0.75, marker=dict(colors=['#0068c9', '#e2e8f0']), textinfo='none')])
        fig.update_layout(annotations=[dict(text=f"<b>{progress_percentage}%</b>", x=0.5, y=0.5, font_size=24, showarrow=False, font=dict(color="#0068c9"))], showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=130, paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- ACTIVE TASK UI ---
    if active_count > 0:
        for idx, active_row in running_tasks.iterrows():
            sheet_row = idx + 2
            display_name = str(active_row['Sub_Activities'])
            st.markdown(f"<div style='background-color: #f8f9fa; border-left: 5px solid #0068c9; padding: 12px;'>⏳ <b>{display_name}</b></div>", unsafe_allow_html=True)
            
            task_status = st.selectbox("Update Status:", ["In Progress", "Completed"], key=f"status_{sheet_row}")
            if st.button("🛑 STOP & LOG", key=f"save_{sheet_row}", type="primary"):
                end_time = now.strftime('%H:%M')
                
                # 1. Update MY ROUTINE 2026
                main_ss = get_main_spreadsheet()
                main_ss.worksheet("activity_log").update_cell(sheet_row, 3, end_time)
                
                # Setup target identifiers
                mdm_ss = get_mdm_spreadsheet()
                parts = display_name.split(" | ", 1)
                target_sheet = parts[0].strip()
                target_work = parts[1].strip() if len(parts) > 1 else ""
                
                # 2. Update CONFIG Status & Get Month from Config
                config_ws = mdm_ss.worksheet("CONFIG")
                config_list = config_ws.get_all_records()
                task_month = st.session_state.selected_month
                
                for i, row in enumerate(config_list):
                    if get_clean_val(row, 'Sheet') == target_sheet and get_clean_val(row, 'Work') == target_work:
                        found_month = get_clean_val(row, 'Month')
                        if found_month: 
                            task_month = found_month
                        # Log selected status to Status column (D is 4)
                        config_ws.update_cell(i + 2, 4, task_status.upper())
                        break
                
                # 3. Locate and update the RUNNING row in MDM LOGS tab
                logs_ws = mdm_ss.get_worksheet(0)
                logs_data = logs_ws.get_all_values()
                log_row_idx = None
                
                # Search backward through the logs to find the active "RUNNING" entry
                for i in range(len(logs_data)-1, -1, -1):
                    row = logs_data[i]
                    if len(row) >= 5 and str(row[0]).strip() == target_sheet and str(row[1]).strip() == target_work and str(row[4]).strip() == "RUNNING":
                        log_row_idx = i + 1
                        break
                
                # Update Stop time (E), Month (G), and Status (H) in the specific LOGS row
                if log_row_idx:
                    try:
                        logs_ws.update(range_name=f"E{log_row_idx}", values=[[end_time]], value_input_option="USER_ENTERED")
                        logs_ws.update(range_name=f"G{log_row_idx}:H{log_row_idx}", values=[[task_month, task_status.upper()]], value_input_option="USER_ENTERED")
                    except TypeError:
                        logs_ws.update(f"E{log_row_idx}", [[end_time]], value_input_option="USER_ENTERED")
                        logs_ws.update(f"G{log_row_idx}:H{log_row_idx}", [[task_month, task_status.upper()]], value_input_option="USER_ENTERED")
                else:
                    # Failsafe append (A-H columns)
                    smart_append_row(logs_ws, [target_sheet, target_work, mdm_date_str, active_row['Start_Time'], end_time, MDM_GS_FORMULA, task_month, task_status.upper()])
                
                get_activity_log.clear()
                fetch_mdm_raw_data.clear()
                st.rerun()

    if active_count == 0:
        selected_task = st.selectbox("Select Task from Config", mdm_tasks_list)
        if st.button("▶️ Start Task", type="primary", use_container_width=True):
            if "All MDM tasks" not in selected_task:
                parts = selected_task.split(" | ", 1)
                target_sheet = parts[0].strip()
                target_work = parts[1].strip() if len(parts) > 1 else ""

                # Look up the task's active Month safely
                task_month = st.session_state.selected_month
                for row in config_raw:
                    if get_clean_val(row, 'Sheet') == target_sheet and get_clean_val(row, 'Work') == target_work:
                        found_month = get_clean_val(row, 'Month')
                        if found_month: 
                            task_month = found_month
                        break
                
                # Log to MY ROUTINE 2026 as RUNNING
                smart_append_row(get_main_spreadsheet().worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "WORK", selected_task, "", "MDM Return Task"])
                
                # Log to MDM RETURN LOG as RUNNING (Month in Col G, Status as IN PROGRESS in Col H)
                smart_append_row(get_mdm_spreadsheet().get_worksheet(0), [target_sheet, target_work, mdm_date_str, now.strftime('%H:%M'), "RUNNING", MDM_GS_FORMULA, task_month, "IN PROGRESS"])
                
                get_activity_log.clear()
                fetch_mdm_raw_data.clear()
                st.rerun()

    # --- MASTER TASK LIST TABLE ---
    st.markdown("""
        <br><hr>
        <div style='display: flex; align-items: center; margin-bottom: 15px;'>
            <span style='font-size: 28px; margin-right: 10px;'>📋</span>
            <span style='background: linear-gradient(120deg, #1e3a8a, #0068c9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 28px; font-weight: 800; letter-spacing: 0.5px;'>Master Task List</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Safely build the table
    table_data = [{"Sheet": get_clean_val(r, 'Sheet'), "Work": get_clean_val(r, 'Work'), "Status": get_clean_val(r, 'Status').title() or "Pending"} for r in config_raw]
    
    if table_data:
        df_table = pd.DataFrame(table_data)
        def highlight_status(row):
            colors = {'Completed': ('#dcfce7','#166534'), 'In Progress': ('#fef08a','#854d0e')}
            bg, txt = colors.get(row['Status'], ('#fee2e2','#991b1b'))
            return [f'background-color: {bg}; color: {txt}; font-weight: 500'] * len(row)
        st.dataframe(df_table.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)

    # --- RESET LOGIC (BATCH UPDATE TO PREVENT 429 ERROR) ---
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("⚙️ Configuration & Monthly Reset"):
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        new_month = st.selectbox("Tracking Month", months, index=months.index(st.session_state.selected_month))
        if new_month != st.session_state.selected_month:
            st.session_state.selected_month = new_month; st.rerun()

        if st.button("🔄 Reset Config for New Month", use_container_width=True):
            try:
                mdm_ss = get_mdm_spreadsheet()
                config_ws = mdm_ss.worksheet("CONFIG")
                rows = config_ws.get_all_values()
                if len(rows) > 1:
                    batch_values = [[new_month, "PENDING"] for _ in range(len(rows) - 1)]
                    config_ws.update(range_name=f"C2:D{len(rows)}", values=batch_values)
                    
                    fetch_mdm_raw_data.clear()
                    st.success(f"Tasks reset for {new_month} {app_year}!")
                    time.sleep(1.5)
                    st.rerun()
            except Exception as e:
                st.error(f"Reset Failed: {e}")

except Exception as e:
    st.error(f"System Error: {e}")
