import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

# --- Master Google Sheets Formulas for Duration ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'[cite: 5]
MDM_GS_FORMULA = '=IF(INDIRECT("E"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("E"&ROW())-INDIRECT("D"&ROW()), 1), "h:mm"), ""))'[cite: 5]

# ==========================================
# 1. Configuration & Session State Init
# ==========================================
st.set_page_config(page_title="MDM Return Logger", page_icon="📦", layout="wide")[cite: 5]

# --- BACK BUTTON (PRESERVED IN STRICT LOCATION) ---
if st.button("⬅️ Back to Dashboard", type="secondary"):[cite: 5]
    st.switch_page("dashboard.py")[cite: 5]
st.write("---") 
# --------------------------------------------------

if 'pomodoro_state' not in st.session_state:[cite: 5]
    st.session_state.pomodoro_state = {}[cite: 5]

# State for Selected Month[cite: 5]
if 'selected_month' not in st.session_state:[cite: 5]
    st.session_state.selected_month = datetime.now().strftime("%B")[cite: 5]

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
""", unsafe_allow_html=True)[cite: 5]

# ==========================================
# 2. Database Connection & Caching Helpers
# ==========================================
@st.cache_resource
def init_connection():[cite: 5]
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"][cite: 5]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)[cite: 5]
    return gspread.authorize(creds)[cite: 5]

@st.cache_resource
def get_main_spreadsheet():[cite: 5]
    client = init_connection()[cite: 5]
    return client.open("MY ROUTINE 2026")[cite: 5]

@st.cache_resource
def get_mdm_spreadsheet():[cite: 5]
    client = init_connection()[cite: 5]
    return client.open("MDM RETURN LOG")[cite: 5]

def smart_append_row(sheet, row_data):[cite: 5]
    col_a = sheet.col_values(1)[cite: 5]
    next_row = len(col_a) + 1[cite: 5]
    try:[cite: 5]
        sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")[cite: 5]
    except TypeError:[cite: 5]
        sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")[cite: 5]

@st.cache_data(ttl=300)
def get_activity_log():[cite: 5]
    ss = get_main_spreadsheet()[cite: 5]
    sheet = ss.worksheet("activity_log")[cite: 5]
    data = sheet.get_all_values()[cite: 5]
    if len(data) <= 1:[cite: 5]
        return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])[cite: 5]
    df = pd.DataFrame(data[1:], columns=data[0])[cite: 5]
    while df.shape[1] < 8: df[df.shape[1]] = ""[cite: 5]
    df = df.iloc[:, :8][cite: 5]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"][cite: 5]
    df = df[df["Date"].astype(str).str.strip() != ""][cite: 5]
    return df[cite: 5]

@st.cache_data(ttl=300)
def fetch_mdm_raw_data():[cite: 5]
    try:[cite: 5]
        ss = get_mdm_spreadsheet()[cite: 5]
        config_data = ss.worksheet("CONFIG").get_all_records()[cite: 5]
        log_data = ss.get_worksheet(0).get_all_values()[cite: 5]
        return config_data, log_data[cite: 5]
    except Exception as e:[cite: 5]
        st.error(f"Failed to fetch MDM data: {e}")[cite: 5]
        return [], [][cite: 5]

def get_mdm_tasks(config_data, log_data):[cite: 5]
    if not config_data: return ["Error loading tasks"][cite: 5]
    all_tasks = [][cite: 5]
    for row in config_data:[cite: 5]
        sheet_val = str(row.get('Sheet', '')).strip()[cite: 5]
        work_val = str(row.get('Work', '')).strip()[cite: 5]
        # Logic to hide already completed tasks in Config[cite: 5]
        if (sheet_val or work_val) and str(row.get('Status', '')).upper() != "COMPLETED":[cite: 5]
            all_tasks.append(f"{sheet_val} | {work_val}")[cite: 5]
    if not all_tasks: return ["🎉 All MDM tasks completed!"][cite: 5]
    return all_tasks[cite: 5]

# ==========================================
# 3. Main Application Logic
# ==========================================
ist_timezone = pytz.timezone('Asia/Kolkata')[cite: 5]
now = datetime.now(ist_timezone)[cite: 5]
today_str = now.strftime('%Y-%m-%d')[cite: 5]
mdm_date_str = now.strftime('%d-%b-%Y')[cite: 5]

try:[cite: 5]
    log_df = get_activity_log()[cite: 5]
    config_raw, log_raw = fetch_mdm_raw_data()[cite: 5]
    mdm_tasks_list = get_mdm_tasks(config_raw, log_raw)[cite: 5]
    
    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Notes'] == 'MDM Return Task')][cite: 5]
    active_count = len(running_tasks)[cite: 5]

    # --- PROGRESS CALCULATION ---
    total_tasks = len(config_raw)[cite: 5]
    completed_count = sum(1 for row in config_raw if str(row.get('Status', '')).upper() == "COMPLETED")[cite: 5]
    progress_percentage = int((completed_count / total_tasks) * 100) if total_tasks > 0 else 0[cite: 5]

    # --- HEADER & SYNC ---
    col_title, col_sync = st.columns([4, 1])[cite: 5]
    with col_title:[cite: 5]
        st.markdown(f"<h1 style='margin-top: 0px;'>📦 MDM RETURN PREPARE ({st.session_state.selected_month})</h1>", unsafe_allow_html=True)[cite: 5]
    with col_sync:[cite: 5]
        if st.button("🔄 Sync", use_container_width=True):[cite: 5]
            get_activity_log.clear(); fetch_mdm_raw_data.clear(); st.rerun()[cite: 5]

    # --- PROGRESS BOX ---
    st.markdown("""<div id="progress_box_anchor"></div><style>div.element-container:has(#progress_box_anchor) + div[data-testid="stHorizontalBlock"] { background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%); border: 1px solid #7dd3fc; border-radius: 16px; padding: 15px 25px; align-items: center; margin-bottom: 25px; margin-top: 15px; }</style>""", unsafe_allow_html=True)[cite: 5]
    col_text, col_chart = st.columns([1.5, 1])[cite: 5]
    with col_text:[cite: 5]
        st.markdown(f"<h3 style='margin: 0; color: #1e3a8a;'>Progress</h3><p style='color: #64748b;'>{completed_count} of {total_tasks} finished</p>", unsafe_allow_html=True)[cite: 5]
    with col_chart:[cite: 5]
        import plotly.graph_objects as go[cite: 5]
        fig = go.Figure(data=[go.Pie(values=[progress_percentage, 100-progress_percentage], hole=0.75, marker=dict(colors=['#0068c9', '#e2e8f0']), textinfo='none')])[cite: 5]
        fig.update_layout(annotations=[dict(text=f"<b>{progress_percentage}%</b>", x=0.5, y=0.5, font_size=24, showarrow=False, font=dict(color="#0068c9"))], showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=130, paper_bgcolor='rgba(0,0,0,0)')[cite: 5]
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})[cite: 5]

    # --- ACTIVE TASK UI ---
    if active_count > 0:[cite: 5]
        for idx, active_row in running_tasks.iterrows():[cite: 5]
            sheet_row = idx + 2[cite: 5]
            display_name = str(active_row['Sub_Activities'])[cite: 5]
            st.markdown(f"<div style='background-color: #f8f9fa; border-left: 5px solid #0068c9; padding: 12px;'>⏳ <b>{display_name}</b></div>", unsafe_allow_html=True)[cite: 5]
            
            task_status = st.selectbox("Update Status:", ["In Progress", "Completed"], key=f"status_{sheet_row}")[cite: 5]
            if st.button("🛑 STOP & LOG", key=f"save_{sheet_row}", type="primary"):[cite: 5]
                end_time = now.strftime('%H:%M')[cite: 5]
                main_ss = get_main_spreadsheet()[cite: 5]
                main_ss.worksheet("activity_log").update_cell(sheet_row, 3, end_time)[cite: 5]
                mdm_ss = get_mdm_spreadsheet()[cite: 5]
                parts = display_name.split(" | ", 1)[cite: 5]
                smart_append_row(mdm_ss.get_worksheet(0), [parts[0], parts[1] if len(parts)>1 else "", mdm_date_str, active_row['Start_Time'], end_time, MDM_GS_FORMULA, task_status])[cite: 5]
                
                # Update CONFIG status[cite: 5]
                config_ws = mdm_ss.worksheet("CONFIG")[cite: 5]
                config_list = config_ws.get_all_records()[cite: 5]
                for i, row in enumerate(config_list):[cite: 5]
                    if f"{row['Sheet']} | {row['Work']}" == display_name:[cite: 5]
                        config_ws.update_cell(i + 2, 4, task_status.upper())[cite: 5]
                
                get_activity_log.clear(); fetch_mdm_raw_data.clear(); st.rerun()[cite: 5]

    if active_count == 0:[cite: 5]
        selected_task = st.selectbox("Select Task from Config", mdm_tasks_list)[cite: 5]
        if st.button("▶️ Start Task", type="primary", use_container_width=True):[cite: 5]
            if "All MDM tasks" not in selected_task:[cite: 5]
                smart_append_row(get_main_spreadsheet().worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "WORK", selected_task, "", "MDM Return Task"])[cite: 5]
                get_activity_log.clear(); st.rerun()[cite: 5]

    # --- MASTER TASK LIST TABLE ---
    st.markdown("<br><hr>### 📋 Master Task List", unsafe_allow_html=True)[cite: 5]
    table_data = [{"Sheet": str(r.get('Sheet','')), "Work": str(r.get('Work','')), "Status": str(r.get('Status','PENDING')).title()} for r in config_raw][cite: 5]
    if table_data:[cite: 5]
        df_table = pd.DataFrame(table_data)[cite: 5]
        def highlight_status(row):[cite: 5]
            colors = {'Completed': ('#dcfce7','#166534'), 'In Progress': ('#fef08a','#854d0e')}[cite: 5]
            bg, txt = colors.get(row['Status'], ('#fee2e2','#991b1b'))[cite: 5]
            return [f'background-color: {bg}; color: {txt}; font-weight: 500'] * len(row)[cite: 5]
        st.dataframe(df_table.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)[cite: 5]

    # --- RESET LOGIC (BATCH UPDATE TO PREVENT 429 ERROR)[cite: 5] ---
    st.markdown("<br>", unsafe_allow_html=True)[cite: 5]
    with st.expander("⚙️ Configuration & Monthly Reset"):[cite: 5]
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][cite: 5]
        new_month = st.selectbox("Tracking Month", months, index=months.index(st.session_state.selected_month))[cite: 5]
        if new_month != st.session_state.selected_month:[cite: 5]
            st.session_state.selected_month = new_month; st.rerun()[cite: 5]

        if st.button("🔄 Reset Config for New Month", use_container_width=True):[cite: 5]
            try:[cite: 5]
                mdm_ss = get_mdm_spreadsheet()[cite: 5]
                config_ws = mdm_ss.worksheet("CONFIG")[cite: 5]
                rows = config_ws.get_all_values()[cite: 5]
                if len(rows) > 1:[cite: 5]
                    # BATCH UPDATE: Prepare all values first to avoid multiple API calls[cite: 5]
                    batch_values = [[new_month, "PENDING"] for _ in range(len(rows) - 1)][cite: 5]
                    # One single API call to update the entire month and status range[cite: 5]
                    config_ws.update(range_name=f"C2:D{len(rows)}", values=batch_values)[cite: 5]
                    
                    fetch_mdm_raw_data.clear(); st.success(f"Tasks reset for {new_month}!"); time.sleep(1.5); st.rerun()[cite: 5]
            except Exception as e:[cite: 5]
                st.error(f"Reset Failed: {e}")[cite: 5]

except Exception as e:[cite: 5]
    st.error(f"System Error: {e}")[cite: 5]
