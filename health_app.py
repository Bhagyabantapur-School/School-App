import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

# --- Master Google Sheets Formula for Duration ---
GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

# ==========================================
# 1. Configuration & Session State Init
# ==========================================
st.set_page_config(page_title="Health Tracker", page_icon="🧘", layout="wide")

if 'pomodoro_state' not in st.session_state:
    st.session_state.pomodoro_state = {}

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 0px !important;
        border: 1px solid #cccccc !important;
        background-color: #ffffff !important;
        box-shadow: none !important;
    }
    
    /* CSS for the pulsing dot animation */
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.9; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.9; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Database Connection
# ==========================================
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

@st.cache_resource
def get_main_spreadsheet():
    client = init_connection()
    return client.open("MY ROUTINE 2026")

@st.cache_resource
def get_health_spreadsheet():
    client = init_connection()
    return client.open("Health_log")

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
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

@st.cache_data(ttl=60)
def get_health_categories():
    """Fetches all tab names from the Health_log spreadsheet"""
    try:
        ss = get_health_spreadsheet()
        worksheets = ss.worksheets()
        # Return all tab names except default 'Sheet1' if it's empty and unused
        tabs = [ws.title for ws in worksheets if ws.title != 'Sheet1']
        return tabs
    except Exception as e:
        st.error(f"Error connecting to Health_log: {e}")
        return []

@st.cache_data(ttl=60)
def get_health_category_headers(category_name):
    """Fetches the headers (parameters) for a specific health category"""
    try:
        ss = get_health_spreadsheet()
        sheet = ss.worksheet(category_name)
        headers = sheet.row_values(1)
        return headers
    except Exception:
        return []

# ==========================================
# 3. Main Application Logic
# ==========================================
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)
today_str = now.strftime('%Y-%m-%d')
clean_now = now.replace(second=0, microsecond=0).time()

try:
    log_df = get_activity_log()
    health_categories = get_health_categories()
    
    # Filter for currently running Health Tasks
    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Activity'] == 'HEALTH')]
    active_count = len(running_tasks)

    # --- HEADER & SYNC ---
    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("🧘 Health & Workout Tracker")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Sync Data", use_container_width=True):
            get_activity_log.clear()
            get_health_categories.clear()
            get_health_category_headers.clear()
            st.toast("Synced with Google Sheets!")
            time.sleep(0.5)
            st.rerun()

    # --- FLOATING ACTIVE BADGE ---
    if active_count > 0:
        st.markdown(f"""
            <div style='position: fixed; bottom: 30px; left: 20px; background-color: #2e7b32; color: white; padding: 8px 16px; border-radius: 20px; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); font-weight: bold; font-size: 16px; z-index: 9999; pointer-events: none; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 16px; margin-right: 6px; animation: pulse 1.5s infinite;'>⏱️</span> {active_count} Health Session Active
            </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # SECTION A: LIVE TIME TRACKING & MANUAL LOG
    # ==========================================
    with st.container():
        st.markdown("### ⏱️ Session Tracking")
        st.markdown("---")
        
        # 1. RENDER RUNNING HEALTH TASKS (If any exist)
        if active_count > 0:
            st.markdown("<div style='margin-bottom: 10px; color: #2e7b32;'><b>🟢 Currently Running:</b></div>", unsafe_allow_html=True)
            for idx, active_row in running_tasks.iterrows():
                sheet_row = idx + 2 
                active_sub = str(active_row['Sub_Activities'])
                display_name = active_sub
                
                try:
                    start_dt_str = f"{active_row['Date']} {active_row['Start_Time']}"
                    dt_naive = datetime.strptime(start_dt_str, "%Y-%m-%d %H:%M")
                    active_start_time = ist_timezone.localize(dt_naive)
                    elapsed_time = now - active_start_time
                    mins_elapsed = int(elapsed_time.total_seconds() // 60)
                except: mins_elapsed = 0 
                
                # --- POMODORO LOGIC & BEEP TRIGGER ---
                cycle_minute = mins_elapsed % 30
                pomodoro_count = (mins_elapsed // 30) + 1
                current_state = "Focus" if cycle_minute < 25 else "Break"
                task_id = f"task_{sheet_row}"
                
                if task_id in st.session_state.pomodoro_state:
                    if st.session_state.pomodoro_state[task_id] != current_state:
                        components.html("""
                            <script>
                                try {
                                    var ctx = new (window.AudioContext || window.webkitAudioContext)();
                                    function playBeep(freq, time, dur) {
                                        var osc = ctx.createOscillator();
                                        var gain = ctx.createGain();
                                        osc.connect(gain);
                                        gain.connect(ctx.destination);
                                        osc.frequency.value = freq;
                                        osc.type = "square";
                                        gain.gain.setValueAtTime(0.1, time);
                                        gain.gain.exponentialRampToValueAtTime(0.001, time + dur);
                                        osc.start(time);
                                        osc.stop(time + dur);
                                    }
                                    playBeep(600, ctx.currentTime, 0.2);
                                    playBeep(800, ctx.currentTime + 0.2, 0.3);
                                } catch(e) {}
                            </script>
                        """, height=0, width=0)
                        
                st.session_state.pomodoro_state[task_id] = current_state

                if current_state == "Focus":
                    p_state = "🍅 Activity Time"
                    p_color = "#2e7b32" # Green for Health
                    p_left = 25 - cycle_minute
                    p_prog = cycle_minute / 25.0
                else:
                    p_state = "☕ Rest"
                    p_color = "#1e88e5" # Blue for rest
                    p_left = 30 - cycle_minute
                    p_prog = (cycle_minute - 25) / 5.0
                
                st.markdown(f"""
                <div style='background-color: #f8f9fa; border-left: 5px solid {p_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <strong style='font-size: 16px; color: #333;'>⏳ {display_name}</strong>
                        <span style='color: #666; font-size: 14px;'>Total: {mins_elapsed}m</span>
                    </div>
                    <div style='margin-top: 8px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;'>
                        <span style='color: {p_color}; font-weight: bold; font-size: 14px;'>{p_state} (Cycle {pomodoro_count})</span>
                        <span style='color: #555; font-size: 13px; font-weight: bold;'>{p_left}m left</span>
                    </div>
                    <div style='width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 6px;'>
                        <div style='width: {p_prog * 100}%; background-color: {p_color}; height: 6px; border-radius: 4px; transition: width 0.5s ease;'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Dynamic Parameter Inputs for Saving
                st.markdown("**Log Session Details:**")
                headers = get_health_category_headers(display_name)
                
                # Base headers that are auto-filled
                base_headers = ["Date", "Start_Time", "End_Time", "Duration"]
                custom_params = [h for h in headers if h not in base_headers]
                
                param_values = {}
                if custom_params:
                    cols = st.columns(min(len(custom_params), 4))
                    for i, param in enumerate(custom_params):
                        with cols[i % 4]:
                            # Parse expected type based on bracket hints in header if any 
                            # e.g., "Music [Yes/No]"
                            if "[Drop:" in param:
                                clean_param = param.split("[Drop:")[0].strip()
                                options_raw = param.split("[Drop:")[1].split("]")[0]
                                options = [o.strip() for o in options_raw.split(",")]
                                param_values[param] = st.selectbox(clean_param, options, key=f"live_param_{idx}_{param}")
                            elif "[Check]" in param:
                                clean_param = param.split("[Check]")[0].strip()
                                checked = st.checkbox(clean_param, key=f"live_param_{idx}_{param}")
                                param_values[param] = "Yes" if checked else "No"
                            else:
                                param_values[param] = st.text_input(param, key=f"live_param_{idx}_{param}")

                col_stop, col_cancel = st.columns([1, 1])
                with col_stop:
                    if st.button("🛑 SAVE & LOG", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                        end_time_log = now.time()
                        
                        # 1. Update Main Activity Log
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.update_cell(sheet_row, 3, end_time_log.strftime('%H:%M')) 
                        log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                        
                        # 2. Add Detailed Log to Specific Health Tab
                        health_ss = get_health_spreadsheet()
                        try:
                            target_sheet = health_ss.worksheet(display_name)
                            
                            # Construct the row data based on headers
                            row_data = []
                            for h in headers:
                                if h == "Date": row_data.append(today_str)
                                elif h == "Start_Time": row_data.append(active_row['Start_Time'])
                                elif h == "End_Time": row_data.append(end_time_log.strftime('%H:%M'))
                                elif h == "Duration": row_data.append(GS_FORMULA)
                                else: row_data.append(param_values.get(h, ""))
                                
                            target_sheet.append_row(row_data, value_input_option="USER_ENTERED")
                            
                            get_activity_log.clear() 
                            st.success(f"Saved: Detailed log added to '{display_name}' tab!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to log details to Health_log: {e}")

                with col_cancel:
                    if st.button("❌ CANCEL", key=f"cancel_{sheet_row}", use_container_width=True):
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.delete_rows(sheet_row)
                        get_activity_log.clear() 
                        st.warning(f"Cancelled: {display_name}")
                        time.sleep(1)
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        # 2. START OR LOG A NEW HEALTH SESSION
        if health_categories and active_count == 0:
            tab_live, tab_manual = st.tabs(["⏱️ Live Timer", "📝 Manual Log"])
            
            # --- LIVE TIMER TAB ---
            with tab_live:
                st.markdown("<div style='margin-bottom: 5px; color: #2e7b32;'><b>🚀 Start New Session:</b></div>", unsafe_allow_html=True)
                
                col_cat, col_btn = st.columns([3, 1])
                with col_cat:
                    selected_cat_live = st.selectbox("Select Health Activity", health_categories, label_visibility="collapsed", key="start_cat_sel_live")
                
                with col_btn:
                    st.markdown(
                        """
                        <div id="health_start_anchor"></div>
                        <style>
                        div[data-testid="column"]:nth-of-type(2) div.element-container:has(#health_start_anchor) + div.element-container button {
                            background-color: #2e7b32 !important; 
                            color: white !important;
                            border: none !important;
                        }
                        div[data-testid="column"]:nth-of-type(2) div.element-container:has(#health_start_anchor) + div.element-container button:hover {
                            background-color: #1b5e20 !important; 
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )
                    if st.button("▶️ Start Timer", key="start_health_live", use_container_width=True):
                        # Start logging to Main Activity Log only (details saved on Stop)
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.append_row([
                            today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                            "HEALTH", selected_cat_live, "", "Tracked via Health App Timer"
                        ], value_input_option="USER_ENTERED")
                        
                        get_activity_log.clear() 
                        st.rerun()

            # --- MANUAL LOG TAB ---
            with tab_manual:
                st.markdown("<div style='margin-bottom: 5px; color: #555;'><b>📝 Record Completed Activity:</b></div>", unsafe_allow_html=True)
                
                selected_cat_manual = st.selectbox("Select Health Activity", health_categories, key="start_cat_sel_manual")
                
                # Fetch parameters for the selected category so user can fill them out now
                m_headers = get_health_category_headers(selected_cat_manual)
                m_base_headers = ["Date", "Start_Time", "End_Time", "Duration"]
                m_custom_params = [h for h in m_headers if h not in m_base_headers]
                
                col_md, col_ms, col_me = st.columns([2, 1, 1])
                with col_md: m_date = st.date_input("Date", value=now.date(), key="manual_date")
                with col_ms: m_start = st.time_input("Start Time", value=clean_now, key="manual_start")
                with col_me: m_end = st.time_input("End Time", value=clean_now, key="manual_end")
                
                m_param_values = {}
                if m_custom_params:
                    st.markdown("**Activity Details:**")
                    m_cols = st.columns(min(len(m_custom_params), 4))
                    for i, param in enumerate(m_custom_params):
                        with m_cols[i % 4]:
                            if "[Drop:" in param:
                                clean_param = param.split("[Drop:")[0].strip()
                                options_raw = param.split("[Drop:")[1].split("]")[0]
                                options = [o.strip() for o in options_raw.split(",")]
                                m_param_values[param] = st.selectbox(clean_param, options, key=f"man_param_{param}")
                            elif "[Check]" in param:
                                clean_param = param.split("[Check]")[0].strip()
                                checked = st.checkbox(clean_param, key=f"man_param_{param}")
                                m_param_values[param] = "Yes" if checked else "No"
                            else:
                                m_param_values[param] = st.text_input(param, key=f"man_param_{param}")
                                
                if st.button("💾 Save Manual Log", use_container_width=True, type="primary"):
                    start_str_m = m_start.strftime('%H:%M')
                    end_str_m = m_end.strftime('%H:%M')
                    date_str_m = m_date.strftime('%Y-%m-%d')
                    
                    # 1. Update Main Activity Log
                    main_ss = get_main_spreadsheet()
                    log_sheet = main_ss.worksheet("activity_log")
                    log_sheet.append_row([
                        date_str_m, start_str_m, end_str_m, GS_FORMULA,    
                        "HEALTH", selected_cat_manual, "", "Manually logged via Health App"
                    ], value_input_option="USER_ENTERED")
                    
                    # 2. Add Detailed Log to Specific Health Tab
                    health_ss = get_health_spreadsheet()
                    try:
                        target_sheet = health_ss.worksheet(selected_cat_manual)
                        
                        row_data = []
                        for h in m_headers:
                            if h == "Date": row_data.append(date_str_m)
                            elif h == "Start_Time": row_data.append(start_str_m)
                            elif h == "End_Time": row_data.append(end_str_m)
                            elif h == "Duration": row_data.append(GS_FORMULA)
                            else: row_data.append(m_param_values.get(h, ""))
                            
                        target_sheet.append_row(row_data, value_input_option="USER_ENTERED")
                        
                        get_activity_log.clear() 
                        st.success(f"Saved: Detailed log added to '{selected_cat_manual}' tab!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to log details to Health_log: {e}")

        elif not health_categories:
            st.info("No Health categories found. Create one below to get started!")

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # ==========================================
    # SECTION B: CATEGORY & PARAMETER MANAGER
    # ==========================================
    with st.container():
        st.markdown("### ⚙️ Health Log Configuration")
        
        with st.expander("➕ Create New Health Category", expanded=not health_categories):
            with st.form("new_health_cat_form", clear_on_submit=True):
                st.markdown("This will create a new tab in your `Health_log` Google Sheet.")
                new_cat_name = st.text_input("Activity Name (e.g., MEDITATION, YOGA, RUNNING)").upper()
                
                st.markdown("#### Add Custom Tracking Parameters")
                st.markdown("""
                *Tips for adding parameters:*
                * **Text/Number Input:** Just type the name (e.g., `Heart Rate`, `Distance (km)`)
                * **Dropdown:** Add `[Drop: Option1, Option2]` (e.g., `Music [Drop: Calm, Focus, None]`)
                * **Checkbox:** Add `[Check]` (e.g., `Stretched After [Check]`)
                """)
                
                col1, col2 = st.columns(2)
                with col1: param_1 = st.text_input("Parameter 1", placeholder="e.g., Heart Rate")
                with col2: param_2 = st.text_input("Parameter 2", placeholder="e.g., Music [Drop: Yes, No]")
                
                col3, col4 = st.columns(2)
                with col3: param_3 = st.text_input("Parameter 3", placeholder="e.g., Felt Good [Check]")
                with col4: param_4 = st.text_input("Parameter 4")
                
                if st.form_submit_button("Create Category", use_container_width=True, type="primary"):
                    if new_cat_name.strip():
                        try:
                            health_ss = get_health_spreadsheet()
                            
                            # Standard Headers
                            headers = ["Date", "Start_Time", "End_Time", "Duration"]
                            
                            # Add user-defined params
                            params = [p.strip() for p in [param_1, param_2, param_3, param_4] if p.strip()]
                            headers.extend(params)
                            
                            try:
                                new_sheet = health_ss.add_worksheet(title=new_cat_name.strip(), rows="1000", cols=str(max(len(headers), 5)))
                                new_sheet.append_row(headers)
                                get_health_categories.clear()
                                get_health_category_headers.clear()
                                st.success(f"Success! '{new_cat_name}' tab created in Health_log.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error creating tab (It might already exist): {e}")
                                
                        except Exception as e:
                            st.error(f"System Error: {e}")
                    else:
                        st.error("Please provide an Activity Name.")

except Exception as e:
    st.error(f"Critical System Error: Make sure your 'Health_log' Google Sheet exists and is shared with your service account. Details: {e}")
