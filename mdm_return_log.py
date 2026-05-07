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
        data_tab_data = ss.worksheet("Data").get_all_records()
        return config_data, log_data, data_tab_data
    except Exception as e:
        st.error(f"Failed to fetch MDM data: {e}")
        return [], [], []

# --- SAFEGUARD FUNCTION ---
def get_clean_val(row_dict, target_key):
    for k, v in row_dict.items():
        if str(k).strip().lower() == target_key.strip().lower():
            return str(v).strip()
    return ""

# ==========================================
# 3. Main Application Logic
# ==========================================
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)
today_str = now.strftime('%Y-%m-%d')
mdm_date_str = now.strftime('%d-%b-%Y') 
months_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

try:
    log_df_raw = get_activity_log()
    config_raw, log_raw, data_raw = fetch_mdm_raw_data()
    
    # --- EXTRACT DATA FROM THE NEW "Data" TAB ---
    app_title = "MDM RETURN PREPARE"
    app_year = now.strftime('%Y')
    default_month = now.strftime('%B')
    
    if data_raw and len(data_raw) > 0:
        raw_title = get_clean_val(data_raw[0], 'Title') or app_title
        app_title = raw_title.split('(')[0].strip() 
        default_month = get_clean_val(data_raw[0], 'Month') or default_month
        app_year = get_clean_val(data_raw[0], 'Year') or app_year

    # Set the session state month ONLY AFTER reading the Data tab
    if 'selected_month' not in st.session_state:
        st.session_state.selected_month = default_month

    # --- PROCESS LOGS INTO DATAFRAME ---
    if log_raw and len(log_raw) > 1:
        clean_logs = []
        for r in log_raw[1:]:
            row = r + [""] * (8 - len(r)) # Pad if short to ensure 8 columns
            clean_logs.append(row[:8])
        df_logs = pd.DataFrame(clean_logs, columns=['Sheet', 'Work', 'Date', 'Start', 'Stop', 'Duration', 'Month', 'Status'])
        df_logs['Sheet'] = df_logs['Sheet'].astype(str).str.strip()
        df_logs['Work'] = df_logs['Work'].astype(str).str.strip()
        df_logs['Month'] = df_logs['Month'].astype(str).str.strip()
        df_logs['Status'] = df_logs['Status'].astype(str).str.strip().str.upper()
    else:
        df_logs = pd.DataFrame(columns=['Sheet', 'Work', 'Date', 'Start', 'Stop', 'Duration', 'Month', 'Status'])

    # --- BUILD MASTER TASK SET ---
    master_tasks = []
    for row in config_raw:
        s = get_clean_val(row, 'Sheet')
        w = get_clean_val(row, 'Work')
        if s or w:
            master_tasks.append({"Sheet": s, "Work": w})
    total_tasks = len(master_tasks)

    # --- CALCULATE CURRENT MONTH STATUS DYNAMICALLY FROM LOGS ---
    table_data = []
    selected_m_logs = df_logs[df_logs['Month'] == st.session_state.selected_month].drop_duplicates(subset=['Sheet', 'Work'], keep='last')
    status_map = {}
    for _, row in selected_m_logs.iterrows():
        status_map[(row['Sheet'], row['Work'])] = row['Status'].title()

    completed_count = 0
    available_tasks_list = []
    
    for task in master_tasks:
        s = task["Sheet"]
        w = task["Work"]
        current_status = status_map.get((s, w), "Pending")
        
        table_data.append({
            "Sheet": s,
            "Work": w,
            "Status": current_status
        })
        
        if current_status.upper() == "COMPLETED":
            completed_count += 1
        else:
            available_tasks_list.append(f"{s} | {w}")

    if not available_tasks_list: available_tasks_list = ["🎉 All MDM tasks completed!"]
    progress_percentage = int((completed_count / total_tasks) * 100) if total_tasks > 0 else 0

    running_tasks = log_df_raw[(log_df_raw['End_Time'] == 'RUNNING') & (log_df_raw['Notes'] == 'MDM Return Task')]
    active_count = len(running_tasks)

    # ==========================================
    # TABS SETUP
    # ==========================================
    tab_dashboard, tab_overview, tab_settings = st.tabs(["📦 Dashboard", "📊 Monthly Overview", "⚙️ Settings"])

    with tab_dashboard:
        # --- HEADER & SYNC ---
        col_title, col_sync = st.columns([4, 1])
        with col_title:
            st.markdown(f"<h1 style='margin-top: 0px;'>📦 {app_title} ({st.session_state.selected_month} {app_year})</h1>", unsafe_allow_html=True)
        with col_sync:
            if st.button("🔄 Sync", use_container_width=True):
                get_activity_log.clear(); fetch_mdm_raw_data.clear(); st.rerun()

        # --- PROGRESS BOX ---
        st.markdown("""<div id="progress_box_anchor"></div><style>div.element-container:has(#progress_box_anchor) + div[data-testid="stHorizontalBlock"] { background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%); border: 1px solid #7dd3fc; border-radius: 16px; padding: 15px 25px; align-items: center; margin-bottom: 25px; margin-top: 15px; }</style>""", unsafe_allow_html=True)
        col_text, col_chart = st.columns([1.5, 1])
        with col_text:
            st.markdown(f"<h3 style='margin: 0; color: #1e3a8a;'>Progress</h3><p style='color: #64748b;'>{completed_count} of {total_tasks} finished for {st.session_state.selected_month}</p>", unsafe_allow_html=True)
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
                    
                    main_ss = get_main_spreadsheet()
                    main_ss.worksheet("activity_log").update_cell(sheet_row, 3, end_time)
                    
                    mdm_ss = get_mdm_spreadsheet()
                    parts = display_name.split(" | ", 1)
                    target_sheet = parts[0].strip()
                    target_work = parts[1].strip() if len(parts) > 1 else ""
                    
                    config_ws = mdm_ss.worksheet("CONFIG")
                    config_list = config_ws.get_all_records()
                    task_month = st.session_state.selected_month
                    
                    for i, row in enumerate(config_list):
                        if get_clean_val(row, 'Sheet') == target_sheet and get_clean_val(row, 'Work') == target_work:
                            # Still write to CONFIG as a quick cache/backup, but Dashboard reads LOGS natively now
                            config_ws.update_cell(i + 2, 4, task_status.upper())
                            break
                    
                    logs_ws = mdm_ss.get_worksheet(0)
                    logs_data = logs_ws.get_all_values()
                    log_row_idx = None
                    
                    for i in range(len(logs_data)-1, -1, -1):
                        row = logs_data[i]
                        if len(row) >= 5 and str(row[0]).strip() == target_sheet and str(row[1]).strip() == target_work and str(row[4]).strip() == "RUNNING":
                            log_row_idx = i + 1
                            break
                    
                    if log_row_idx:
                        try:
                            logs_ws.update(range_name=f"E{log_row_idx}", values=[[end_time]], value_input_option="USER_ENTERED")
                            logs_ws.update(range_name=f"G{log_row_idx}:H{log_row_idx}", values=[[task_month, task_status.upper()]], value_input_option="USER_ENTERED")
                        except TypeError:
                            logs_ws.update(f"E{log_row_idx}", [[end_time]], value_input_option="USER_ENTERED")
                            logs_ws.update(f"G{log_row_idx}:H{log_row_idx}", [[task_month, task_status.upper()]], value_input_option="USER_ENTERED")
                    else:
                        smart_append_row(logs_ws, [target_sheet, target_work, mdm_date_str, active_row['Start_Time'], end_time, MDM_GS_FORMULA, task_month, task_status.upper()])
                    
                    get_activity_log.clear()
                    fetch_mdm_raw_data.clear()
                    st.rerun()

        if active_count == 0:
            selected_task = st.selectbox("Select Task to Start", available_tasks_list)
            if st.button("▶️ Start Task", type="primary", use_container_width=True):
                if "All MDM tasks" not in selected_task:
                    parts = selected_task.split(" | ", 1)
                    target_sheet = parts[0].strip()
                    target_work = parts[1].strip() if len(parts) > 1 else ""

                    task_month = st.session_state.selected_month
                    
                    smart_append_row(get_main_spreadsheet().worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "WORK", selected_task, "", "MDM Return Task"])
                    smart_append_row(get_mdm_spreadsheet().get_worksheet(0), [target_sheet, target_work, mdm_date_str, now.strftime('%H:%M'), "RUNNING", MDM_GS_FORMULA, task_month, "IN PROGRESS"])
                    
                    get_activity_log.clear()
                    fetch_mdm_raw_data.clear()
                    st.rerun()

        # --- DYNAMIC MASTER TASK LIST TABLE ---
        st.markdown("""
            <br><hr>
            <div style='display: flex; align-items: center; margin-bottom: 15px;'>
                <span style='font-size: 28px; margin-right: 10px;'>📋</span>
                <span style='background: linear-gradient(120deg, #1e3a8a, #0068c9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 28px; font-weight: 800; letter-spacing: 0.5px;'>Task List (LOGS Sync)</span>
            </div>
        """, unsafe_allow_html=True)
        
        if table_data:
            df_table = pd.DataFrame(table_data)
            def highlight_status(row):
                colors = {'Completed': ('#dcfce7','#166534'), 'In Progress': ('#fef08a','#854d0e'), 'Pending': ('#fee2e2','#991b1b')}
                bg, txt = colors.get(row['Status'], ('#fee2e2','#991b1b'))
                return [f'background-color: {bg}; color: {txt}; font-weight: 500'] * len(row)
            st.dataframe(df_table.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)

    # ==========================================
    # TAB 2: MONTHLY OVERVIEW (NEW)
    # ==========================================
    with tab_overview:
        st.markdown(f"## 📊 Yearly Overview ({app_year})")
        st.write("Visual completion status based on historical LOGS data.")
        
        # Create a 3x4 Grid (4 columns, 3 rows)
        cols = st.columns(4)
        
        for i, m in enumerate(months_list):
            m_logs = df_logs[df_logs['Month'] == m]
            
            bg_color = "#ffffff" # Default White/Grey
            border_color = "#e2e8f0"
            text_color = "#94a3b8"
            completed_in_month = 0
            
            if not m_logs.empty:
                latest_logs = m_logs.drop_duplicates(subset=['Sheet', 'Work'], keep='last')
                in_progress_count = 0
                
                for _, row in latest_logs.iterrows():
                    # Only count tasks that are part of the required master CONFIG list
                    if {"Sheet": row['Sheet'], "Work": row['Work']} in master_tasks:
                        if row['Status'] == "COMPLETED":
                            completed_in_month += 1
                        elif row['Status'] == "IN PROGRESS" or row['Status'] == "RUNNING":
                            in_progress_count += 1
                
                if completed_in_month == total_tasks and total_tasks > 0:
                    bg_color = "#dcfce7" # Light Green
                    border_color = "#86efac"
                    text_color = "#166534"
                elif completed_in_month > 0 or in_progress_count > 0:
                    bg_color = "#fef08a" # Light Yellow
                    border_color = "#fde047"
                    text_color = "#854d0e"
                else:
                    # Logs exist, but no valid task statuses found
                    text_color = "#64748b"
            
            # Use modular math to wrap columns correctly
            col = cols[i % 4]
            with col:
                st.markdown(f"""
                <div style="background-color: {bg_color}; border: 2px solid {border_color}; border-radius: 12px; padding: 20px 10px; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
                    <h2 style="margin:0; color: {text_color}; font-size: 24px; font-weight: 800;">{m[:3].upper()}</h2>
                    <span style="font-size: 13px; color: {text_color}; font-weight: 600;">{completed_in_month} / {total_tasks} Done</span>
                </div>
                """, unsafe_allow_html=True)


    # ==========================================
    # TAB 3: SETTINGS & RESET
    # ==========================================
    with tab_settings:
        st.markdown("### ⚙️ Configuration & Monthly Reset")
        
        fallback_month = st.session_state.selected_month if st.session_state.selected_month in months_list else "January"
        new_month = st.selectbox("Select Target Month", months_list, index=months_list.index(fallback_month))
        
        if new_month != st.session_state.selected_month:
            st.session_state.selected_month = new_month
            st.rerun()

        st.warning("Clicking the reset button below resets the CONFIG cache to Pending. Your historical LOGS tab remains perfectly safe.")
        if st.button("🔄 Reset Config for Target Month", use_container_width=True):
            try:
                mdm_ss = get_mdm_spreadsheet()
                config_ws = mdm_ss.worksheet("CONFIG")
                rows = config_ws.get_all_values()
                if len(rows) > 1:
                    batch_values = [[new_month, "PENDING"] for _ in range(len(rows) - 1)]
                    config_ws.update(range_name=f"C2:D{len(rows)}", values=batch_values)
                    
                    fetch_mdm_raw_data.clear()
                    st.success(f"Cache reset for {new_month} {app_year}!")
                    time.sleep(1.5)
                    st.rerun()
            except Exception as e:
                st.error(f"Reset Failed: {e}")

except Exception as e:
    st.error(f"System Error: {e}")
