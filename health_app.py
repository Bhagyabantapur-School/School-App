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
    
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.9; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.9; }
    }
    
    details > summary {
      list-style: none;
    }
    details > summary::-webkit-details-marker {
      display: none;
    }
    
    /* Mobile specific adjustments */
    @media (max-width: 640px) {
        /* Ensure the title doesn't get squished */
        .stHeadingContainer h1 {
            font-size: 1.8rem !important;
        }
        /* Add some breathing room for buttons on mobile */
        div.stButton > button {
            margin-top: 5px;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Database Connection & Helpers
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

def smart_append_row(sheet, row_data):
    """Safely appends a row by finding the true end of Column A, avoiding formatting bugs."""
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
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    return df

@st.cache_data(ttl=300)
def get_health_categories():
    try:
        ss = get_health_spreadsheet()
        worksheets = ss.worksheets()
        tabs = [ws.title for ws in worksheets if ws.title not in ['Sheet1', 'Update']]
        return tabs
    except Exception as e:
        st.error(f"Error connecting to Health_log: {e}")
        return []

@st.cache_data(ttl=300)
def get_health_category_headers(category_name):
    try:
        ss = get_health_spreadsheet()
        sheet = ss.worksheet(category_name)
        headers = sheet.row_values(1)
        return headers
    except Exception:
        return []

@st.cache_data(ttl=300)
def get_health_category_data(category_name):
    try:
        ss = get_health_spreadsheet()
        sheet = ss.worksheet(category_name)
        data = sheet.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame()
        df = pd.DataFrame(data[1:], columns=data[0])
        df = df[df[df.columns[0]].astype(str).str.strip() != ""] 
        return df
    except Exception:
        return pd.DataFrame()

def parse_duration_to_minutes(dur_str):
    try:
        h, m = map(int, str(dur_str).strip().split(':'))
        return (h * 60) + m
    except: 
        return 0

def get_last_done_str(item_name, log_df, now, col_name='Sub_Activities'):
    completed_logs = log_df[log_df['End_Time'] != 'RUNNING']
    matches = completed_logs[completed_logs[col_name].astype(str).str.strip().str.upper() == item_name.upper()]
    if matches.empty: return "Never"
    
    max_dt = None
    for _, r in matches.iterrows():
        try:
            dt_str = f"{r['Date']} {r['End_Time']}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            if max_dt is None or dt > max_dt: max_dt = dt
        except: continue
        
    if not max_dt: return "Never"
    
    now_naive = now.replace(tzinfo=None)
    diff = now_naive - max_dt
    
    if diff.days > 0: return f"{diff.days}d ago"
    elif diff.seconds >= 3600: return f"{diff.seconds // 3600}h ago"
    elif diff.seconds >= 60: return f"{diff.seconds // 60}m ago"
    else: return "Just now"

def delete_log_entry(date_str, start_time_str, cat_name):
    try:
        health_ss = get_health_spreadsheet()
        cat_sheet = health_ss.worksheet(cat_name)
        cat_data = cat_sheet.get_all_values()
        
        row_del_health = None
        for idx, row in enumerate(cat_data):
            if idx > 0 and row[0] == date_str and row[1] == start_time_str:
                row_del_health = idx + 1 
                break
                
        if row_del_health:
            cat_sheet.delete_rows(row_del_health)

        main_ss = get_main_spreadsheet()
        log_sheet = main_ss.worksheet("activity_log")
        log_data = log_sheet.get_all_values()
        
        row_del_main = None
        for idx, row in enumerate(log_data):
            if idx > 0 and row[0] == date_str and row[1] == start_time_str and str(row[4]).strip().upper() == "HEALTH" and str(row[5]).strip().upper() == cat_name.upper():
                row_del_main = idx + 1
                break
                
        if row_del_main:
            log_sheet.delete_rows(row_del_main)

        get_activity_log.clear()
        get_health_category_data.clear()
        return True
    except Exception as e:
        st.error(f"Failed to delete record: {e}")
        return False

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
    
    running_tasks = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Activity'] == 'HEALTH')]
    active_count = len(running_tasks)

    # --- HEADER & SYNC (MOBILE RESPONSIVE FIX) ---
    # Using vertical flow instead of strict columns to prevent overlap on small screens
    st.title("🧘 Health Tracker")
    
    # Place sync button below title on mobile, or alongside on desktop
    if st.button("🔄 Sync Data", use_container_width=True):
        get_activity_log.clear()
        get_health_categories.clear()
        get_health_category_headers.clear()
        get_health_category_data.clear()
        st.toast("Synced with Google Sheets!")
        time.sleep(1.0)
        st.rerun()
        
    st.markdown("---")

    # --- FLOATING ACTIVE BADGE ---
    if active_count > 0:
        st.markdown(f"""
            <div style='position: fixed; bottom: 30px; left: 20px; background-color: #2e7b32; color: white; padding: 8px 16px; border-radius: 20px; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); font-weight: bold; font-size: 16px; z-index: 9999; pointer-events: none; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 16px; margin-right: 6px; animation: pulse 1.5s infinite;'>⏱️</span> {active_count} Health Session Active
            </div>
        """, unsafe_allow_html=True)

    with st.container():
        
        # 1. RENDER RUNNING HEALTH TASKS
        if active_count > 0:
            st.markdown("### ⏱️ Active Session")
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
                    p_color = "#2e7b32"
                    p_left = 25 - cycle_minute
                    p_prog = cycle_minute / 25.0
                else:
                    p_state = "☕ Rest"
                    p_color = "#1e88e5"
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
                
                st.markdown("**Log Details:**")
                headers = get_health_category_headers(display_name)
                
                base_headers = ["Date", "Start_Time", "End_Time", "Duration"]
                custom_params = [h for h in headers if h not in base_headers]
                
                param_values = {}
                if custom_params:
                    # Using dynamic columns based on screen size (handled automatically by Streamlit)
                    # We just output the inputs directly instead of forcing them into strict columns
                    for param in custom_params:
                        if "[Drop:" in param:
                            clean_param = param.split("[Drop:")[0].strip()
                            options_raw = param.split("[Drop:")[1].split("]")[0]
                            options = ["-- Select --"] + [o.strip() for o in options_raw.split(",")]
                            param_values[param] = st.selectbox(clean_param, options, key=f"live_param_{idx}_{param}")
                        elif "[Check]" in param:
                            clean_param = param.split("[Check]")[0].strip()
                            checked = st.checkbox(clean_param, key=f"live_param_{idx}_{param}")
                            param_values[param] = "Yes" if checked else "No"
                        else:
                            param_values[param] = st.text_input(param, key=f"live_param_{idx}_{param}")

                # Use columns for buttons as they are usually small enough even on mobile
                col_stop, col_cancel = st.columns([1, 1])
                with col_stop:
                    if st.button("🛑 SAVE", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                        has_missing = any(v == "-- Select --" for v in param_values.values())
                        if has_missing:
                            st.error("⚠️ Please select valid options for all dropdowns!")
                        else:
                            end_time_log = now.time()
                            main_ss = get_main_spreadsheet()
                            log_sheet = main_ss.worksheet("activity_log")
                            log_sheet.update_cell(sheet_row, 3, end_time_log.strftime('%H:%M')) 
                            log_sheet.update_cell(sheet_row, 4, GS_FORMULA)                   
                            
                            health_ss = get_health_spreadsheet()
                            try:
                                target_sheet = health_ss.worksheet(display_name)
                                row_data = []
                                for h in headers:
                                    if h == "Date": row_data.append(today_str)
                                    elif h == "Start_Time": row_data.append(active_row['Start_Time'])
                                    elif h == "End_Time": row_data.append(end_time_log.strftime('%H:%M'))
                                    elif h == "Duration": row_data.append(GS_FORMULA)
                                    else: row_data.append(param_values.get(h, ""))
                                    
                                smart_append_row(target_sheet, row_data)
                                
                                get_activity_log.clear() 
                                get_health_category_data.clear()
                                st.success(f"Saved!")
                                time.sleep(1.0)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to log details: {e}")

                with col_cancel:
                    if st.button("❌ CANCEL", key=f"cancel_{sheet_row}", use_container_width=True):
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        log_sheet.delete_rows(sheet_row)
                        
                        get_activity_log.clear() 
                        st.warning(f"Cancelled")
                        time.sleep(1.0)
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        if health_categories and active_count == 0:
            tab_live, tab_manual, tab_summary, tab_history = st.tabs(["⏱️ Live", "📝 Manual", "📈 Summary", "📜 History"])
            
            # --- LIVE TIMER TAB (MOBILE RESPONSIVE FIX) ---
            with tab_live:
                st.markdown("<div style='margin-bottom: 5px; color: #2e7b32;'><b>🚀 Start Session:</b></div>", unsafe_allow_html=True)
                
                # Removed columns here to prevent the dropdown and button from overlapping on mobile
                # Elements will now stack vertically on smaller screens
                selected_cat_live = st.selectbox("Activity", health_categories, key="start_cat_sel_live")
                
                st.markdown(
                    """
                    <div id="health_start_anchor"></div>
                    <style>
                    div.element-container:has(#health_start_anchor) + div.element-container button {
                        background-color: #2e7b32 !important; 
                        color: white !important;
                        border: none !important;
                        margin-top: 10px;
                    }
                    div.element-container:has(#health_start_anchor) + div.element-container button:hover {
                        background-color: #1b5e20 !important; 
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("▶️ Start Timer", key="start_health_live", use_container_width=True):
                    main_ss = get_main_spreadsheet()
                    log_sheet = main_ss.worksheet("activity_log")
                    row_to_add = [
                        today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA,    
                        "HEALTH", selected_cat_live, "", "Tracked via Health App Timer"
                    ]
                    smart_append_row(log_sheet, row_to_add)
                    
                    get_activity_log.clear() 
                    time.sleep(1.0)
                    st.rerun()

            # --- MANUAL LOG TAB (MOBILE RESPONSIVE FIX) ---
            with tab_manual:
                st.markdown("<div style='margin-bottom: 5px; color: #555;'><b>📝 Record Activity:</b></div>", unsafe_allow_html=True)
                
                selected_cat_manual = st.selectbox("Activity", health_categories, key="start_cat_sel_manual")
                
                m_headers = get_health_category_headers(selected_cat_manual)
                m_base_headers = ["Date", "Start_Time", "End_Time", "Duration"]
                m_custom_params = [h for h in m_headers if h not in m_base_headers]
                
                hours_opts = [f"{i:02d}" for i in range(24)]
                mins_opts = [f"{i:02d}" for i in range(60)]
                curr_h = clean_now.strftime('%H')
                curr_m = clean_now.strftime('%M')
                
                m_date = st.date_input("Date", value=now.date(), key="manual_date")
                
                # Simplified time inputs for better mobile stacking
                col_sh, col_sm = st.columns(2)
                with col_sh: 
                    m_start_h = st.selectbox("Start HH", hours_opts, index=hours_opts.index(curr_h), key="man_sh")
                with col_sm: 
                    m_start_m = st.selectbox("Start MM", mins_opts, index=mins_opts.index(curr_m), key="man_sm")
                    
                col_eh, col_em = st.columns(2)
                with col_eh: 
                    m_end_h = st.selectbox("End HH", hours_opts, index=hours_opts.index(curr_h), key="man_eh")
                with col_em: 
                    m_end_m = st.selectbox("End MM", mins_opts, index=mins_opts.index(curr_m), key="man_em")
                
                m_param_values = {}
                if m_custom_params:
                    st.markdown("**Details:**")
                    # Render parameters sequentially to ensure mobile stacking
                    for param in m_custom_params:
                        if "[Drop:" in param:
                            clean_param = param.split("[Drop:")[0].strip()
                            options_raw = param.split("[Drop:")[1].split("]")[0]
                            options = ["-- Select --"] + [o.strip() for o in options_raw.split(",")]
                            m_param_values[param] = st.selectbox(clean_param, options, key=f"man_param_{param}")
                        elif "[Check]" in param:
                            clean_param = param.split("[Check]")[0].strip()
                            checked = st.checkbox(clean_param, key=f"man_param_{param}")
                            m_param_values[param] = "Yes" if checked else "No"
                        else:
                            m_param_values[param] = st.text_input(param, key=f"man_param_{param}")
                                
                if st.button("💾 Save Manual Log", use_container_width=True, type="primary"):
                    
                    has_missing = any(v == "-- Select --" for v in m_param_values.values())
                    if has_missing:
                        st.error("⚠️ Please select valid options!")
                    else:
                        start_str_m = f"{m_start_h}:{m_start_m}"
                        end_str_m = f"{m_end_h}:{m_end_m}"
                        date_str_m = m_date.strftime('%Y-%m-%d')
                        
                        main_ss = get_main_spreadsheet()
                        log_sheet = main_ss.worksheet("activity_log")
                        row_to_add = [
                            date_str_m, start_str_m, end_str_m, GS_FORMULA,    
                            "HEALTH", selected_cat_manual, "", "Manually logged via Health App"
                        ]
                        smart_append_row(log_sheet, row_to_add)
                        
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
                                
                            smart_append_row(target_sheet, row_data)
                            
                            get_activity_log.clear() 
                            get_health_category_data.clear()
                            st.success(f"Saved!")
                            time.sleep(1.0)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to log details: {e}")

            # --- SUMMARY TAB ---
            with tab_summary:
                st.markdown("<div style='margin-bottom: 5px; color: #555;'><b>📊 Today's Overview:</b></div>", unsafe_allow_html=True)
                
                today_completed_categories = []
                html_cards = []
                
                for cat in health_categories:
                    cat_df = get_health_category_data(cat)
                    if cat_df.empty: continue
                    
                    today_data = cat_df[cat_df['Date'] == today_str].copy()
                    if not today_data.empty:
                        today_completed_categories.append(cat.upper())
                        
                        today_data['Total_Minutes'] = today_data['Duration'].apply(parse_duration_to_minutes)
                        total_mins = today_data['Total_Minutes'].sum()
                        session_count = len(today_data)
                        
                        hours, remainder_mins = divmod(total_mins, 60)
                        dur_display = f"{int(hours)}h {int(remainder_mins)}m" if hours > 0 else f"{int(remainder_mins)}m"
                        
                        sessions_html = ""
                        if session_count > 0:
                            for _, row in today_data.iterrows():
                                sessions_html += f"<div style='display: flex; justify-content: space-between; margin-bottom: 4px;'><span>&bull; <b>{row['Start_Time']} to {row['End_Time']}</b></span><em style='color: #666; font-style: italic;'>{row['Duration']}</em></div>"
                        
                        session_badge = f"<span style='font-weight: normal; font-size: 13px; opacity: 0.8; margin-left: 8px;'>{session_count} Sess.</span>" if session_count > 1 else ""
                        
                        box_html = f"<details style='background: linear-gradient(to right, #e8f5e9, #f1f8e9); padding: 6px 14px; border-radius: 8px; border-left: 6px solid #4caf50; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 8px; cursor: pointer;'><summary style='display: flex; justify-content: space-between; align-items: center; outline: none;'><span style='display: flex; align-items: center;'><span style='font-size: 16px; font-weight: bold; color: #2e7b32; letter-spacing: 0.5px;'>{cat.upper()}</span>{session_badge}</span><span style='font-size: 14px; color: #1b5e20; font-weight: 600; background-color: rgba(255,255,255,0.6); padding: 2px 8px; border-radius: 10px;'>⏱️ {dur_display}</span></summary><div style='margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(46, 123, 50, 0.2); font-size: 14px; color: #444; line-height: 1.5;'>{sessions_html}</div></details>"
                        html_cards.append(box_html)
                
                if html_cards:
                    st.markdown("".join(html_cards), unsafe_allow_html=True)
                else:
                    st.info("No activities logged today.")

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("#### ⚠️ Not Done Today")
                
                missing_cats = [c for c in health_categories if c.upper() not in today_completed_categories]
                
                if missing_cats:
                    for cat in missing_cats:
                        last_done = get_last_done_str(cat, log_df, now)
                        st.markdown(f"<div style='background-color:#fff3e0; padding:6px 14px; border-radius:8px; margin-bottom:8px; border-left: 4px solid #ff9800;'><b style='font-size: 15px;'>{cat}</b> <span style='color: #666; font-size: 13px;'>(Last: {last_done})</span></div>", unsafe_allow_html=True)
                else:
                    st.success("Amazing! Touched on all categories today.")

                st.markdown("<br><hr><br>", unsafe_allow_html=True)
                
                # --- NEW CATEGORY (MOBILE RESPONSIVE FIX) ---
                with st.expander("➕ Create New Category", expanded=not health_categories):
                    num_params = st.number_input("Custom params to add?", min_value=0, max_value=20, value=2, step=1)
                    
                    with st.form("new_health_cat_form", clear_on_submit=True):
                        new_cat_name = st.text_input("Activity Name").upper()
                        
                        param_inputs = []
                        if num_params > 0:
                            st.markdown("#### Custom Params")
                            # Removed columns for robust mobile stacking
                            for i in range(num_params):
                                ph = ""
                                if i == 0: ph = "e.g., Heart Rate"
                                elif i == 1: ph = "e.g., Music [Drop: Yes, No]"
                                elif i == 2: ph = "e.g., Felt Good [Check]"
                                param_inputs.append(st.text_input(f"Parameter {i+1}", placeholder=ph, key=f"param_input_{i}"))
                        
                        if st.form_submit_button("Create Category", use_container_width=True, type="primary"):
                            if new_cat_name.strip() and new_cat_name.strip().upper() != 'UPDATE':
                                try:
                                    health_ss = get_health_spreadsheet()
                                    headers = ["Date", "Start_Time", "End_Time", "Duration"]
                                    params = [p.strip() for p in param_inputs if p.strip()]
                                    headers.extend(params)
                                    
                                    try:
                                        new_sheet = health_ss.add_worksheet(title=new_cat_name.strip(), rows="1000", cols=str(max(len(headers), 5)))
                                        smart_append_row(new_sheet, headers)
                                        get_health_categories.clear()
                                        get_health_category_headers.clear()
                                        st.success(f"Created!")
                                        time.sleep(1.0)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error creating tab: {e}")
                                        
                                except Exception as e:
                                    st.error(f"System Error: {e}")
                            elif new_cat_name.strip().upper() == 'UPDATE':
                                st.error("Reserved name.")
                            else:
                                st.error("Provide a name.")

            # --- ACTIVITY HISTORY TAB ---
            with tab_history:
                st.markdown("<div style='margin-bottom: 5px; color: #555;'><b>📜 Activity History:</b></div>", unsafe_allow_html=True)
                
                selected_history_cat = st.selectbox("Select Activity", health_categories, key="history_cat_sel")
                cat_data = get_health_category_data(selected_history_cat)
                
                if not cat_data.empty:
                    cat_data['Parsed_Date'] = pd.to_datetime(cat_data['Date'], errors='coerce')
                    cat_data['Parsed_Time'] = pd.to_datetime(cat_data['Start_Time'], format='%H:%M', errors='coerce').dt.time
                    cat_data = cat_data.sort_values(by=['Parsed_Date', 'Parsed_Time'], ascending=[False, False]).reset_index(drop=True)
                    
                    current_month_year = ""
                    for i in range(len(cat_data)):
                        row = cat_data.iloc[i]
                        p_date = row['Parsed_Date']
                        
                        if pd.isna(p_date): continue
                        m_y = p_date.strftime('%B %Y').upper()
                        day_str = p_date.strftime('%d %a').upper()
                        
                        if m_y != current_month_year:
                            st.markdown(f"<h4 style='color: #2e7b32; margin-top: 20px; border-bottom: 2px solid #c8e6c9; padding-bottom: 5px;'>{m_y}</h4>", unsafe_allow_html=True)
                            current_month_year = m_y
                        
                        base_h = ["Date", "Start_Time", "End_Time", "Duration", "Parsed_Date", "Parsed_Time"]
                        custom_params = [c for c in cat_data.columns if c not in base_h]
                        
                        params_display = []
                        for cp in custom_params:
                            val = row[cp]
                            if pd.notna(val) and str(val).strip() != "":
                                clean_cp = cp.split("[")[0].strip()
                                params_display.append(f"<b>{clean_cp}:</b> {val}")
                                
                        param_html = f"<br><span style='color: #555; font-size: 14px;'>{' | '.join(params_display)}</span>" if params_display else ""
                        
                        col_record, col_del = st.columns([10, 2])
                        with col_record:
                            st.markdown(f"""
                            <div style='display: flex; align-items: flex-start; margin-bottom: 10px; background-color: #f8f9fa; padding: 8px 10px; border-radius: 8px; border-left: 4px solid #81c784;'>
                                <div style='min-width: 80px; text-align: center; background-color: #e8f5e9; padding: 5px; border-radius: 5px; margin-right: 15px;'>
                                    <strong style='color: #2e7b32; font-size: 16px;'>{day_str.split()[0]}</strong><br>
                                    <span style='color: #666; font-size: 12px;'>{day_str.split()[1]}</span>
                                </div>
                                <div style='flex-grow: 1;'>
                                    <strong style='font-size: 16px; color: #333;'>⏱️ {row['Start_Time']} - {row['End_Time']}</strong> <span style='color: #888; font-size: 14px;'>(Dur: {row['Duration']})</span>
                                    {param_html}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        with col_del:
                            del_key = f"del_{row['Date']}_{row['Start_Time']}_{selected_history_cat}"
                            if st.button("🗑️", key=del_key, help="Delete this log"):
                                with st.spinner("Deleting..."):
                                    if delete_log_entry(str(row['Date']), str(row['Start_Time']), selected_history_cat):
                                        st.success("Deleted!")
                                        time.sleep(1.0)
                                        st.rerun()
                        
                        if i < len(cat_data) - 1:
                            next_row = cat_data.iloc[i+1]
                            next_date = next_row['Parsed_Date']
                            if pd.notna(next_date):
                                diff_days = (p_date - next_date).days
                                if diff_days > 1:
                                    st.markdown(f"<div style='text-align: center; color: #9e9e9e; font-size: 13px; margin: 10px 0;'><em>[{diff_days} days gap]</em></div>", unsafe_allow_html=True)
                else:
                    st.info("No records found.")

        elif not health_categories:
            st.info("Create a category below to get started!")
            
            st.markdown("<br><hr><br>", unsafe_allow_html=True)
            with st.expander("➕ Create New Category", expanded=True):
                num_params = st.number_input("Custom params to add?", min_value=0, max_value=20, value=2, step=1)
                
                with st.form("new_health_cat_form_initial", clear_on_submit=True):
                    new_cat_name = st.text_input("Activity Name").upper()
                    
                    param_inputs = []
                    if num_params > 0:
                        st.markdown("#### Custom Params")
                        for i in range(num_params):
                            ph = ""
                            if i == 0: ph = "e.g., Heart Rate"
                            elif i == 1: ph = "e.g., Music [Drop: Yes, No]"
                            elif i == 2: ph = "e.g., Felt Good [Check]"
                            param_inputs.append(st.text_input(f"Parameter {i+1}", placeholder=ph, key=f"init_param_input_{i}"))
                    
                    if st.form_submit_button("Create Category", use_container_width=True, type="primary"):
                        if new_cat_name.strip() and new_cat_name.strip().upper() != 'UPDATE':
                            try:
                                health_ss = get_health_spreadsheet()
                                headers = ["Date", "Start_Time", "End_Time", "Duration"]
                                params = [p.strip() for p in param_inputs if p.strip()]
                                headers.extend(params)
                                
                                try:
                                    new_sheet = health_ss.add_worksheet(title=new_cat_name.strip(), rows="1000", cols=str(max(len(headers), 5)))
                                    smart_append_row(new_sheet, headers)
                                    get_health_categories.clear()
                                    get_health_category_headers.clear()
                                    st.success(f"Success!")
                                    time.sleep(1.0)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error creating tab: {e}")
                                    
                            except Exception as e:
                                st.error(f"System Error: {e}")
                        elif new_cat_name.strip().upper() == 'UPDATE':
                            st.error("Reserved name.")
                        else:
                            st.error("Provide a name.")

except Exception as e:
    st.error(f"Critical System Error: Make sure your 'Health_log' Google Sheet exists. Details: {e}")
