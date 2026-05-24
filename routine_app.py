import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
from streamlit_autorefresh import st_autorefresh

GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

st.set_page_config(page_title="Live Routine Hub", page_icon="⏱️", layout="centered")

if 'active_main_task' not in st.session_state:
    st.session_state.active_main_task = None
    st.session_state.active_sub_task = None
    st.session_state.active_start_time = None

if 'pomodoro_state' not in st.session_state:
    st.session_state.pomodoro_state = {}

st_autorefresh(interval=120000, key="routine_refresh")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 0px !important;
        border: 1px solid #cccccc !important;
        background-color: #ffffff !important;
        box-shadow: none !important;
    }
    input[type="text"], input[type="time"], textarea {
        font-size: 16px !important;
        padding: 8px !important;
        color: #000000 !important;
    }
    div[data-testid="metric-container"] {
        text-align: center; 
        background-color: #f0f2f6; 
        padding: 10px; 
        border-radius: 10px; 
        margin-bottom: 15px;
    }
    div[data-testid="stCheckbox"] label {
        font-size: 18px !important;
        padding-top: 5px;
        padding-bottom: 5px;
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Database Connection & File Cache
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource
def get_cached_sheet(sheet_name):
    return init_connection().open(sheet_name)

def smart_append_row(sheet, row_data, known_row_count=None):
    if known_row_count is not None:
        next_row = known_row_count + 2  
        try: sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
        except TypeError: sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")
    else:
        col_a = sheet.col_values(1)
        next_row = len(col_a) + 1
        try: sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
        except TypeError: sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

def smart_append_multiple(sheet, rows_data):
    if not rows_data: return
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try: sheet.update(range_name=f"A{next_row}", values=rows_data, value_input_option="USER_ENTERED")
    except TypeError: sheet.update(f"A{next_row}", rows_data, value_input_option="USER_ENTERED")

@st.cache_data(ttl=300, show_spinner="⚡ Booting up ecosystem (Ultra-Fast)...") 
def get_all_ecosystem_data():
    main_ss = get_cached_sheet("MY ROUTINE 2026")
    money_ss = get_cached_sheet("sk_money_location")
    
    def process_raw(data, expected_cols, column_names):
        if not data or len(data) <= 1: 
            return pd.DataFrame(columns=column_names)
        records = []
        for row in data[1:]:
            padded_row = row + [""] * (expected_cols - len(row)) if len(row) < expected_cols else row
            records.append(padded_row[:expected_cols])
        return pd.DataFrame(records, columns=column_names)

    try:
        main_ranges = ['routine_master', 'activity_log', 'future_tasks', 'holidays', 'must_do', 'PRE', 'prep_checklists']
        main_res = main_ss.values_batch_get(main_ranges).get('valueRanges', [])
        rm_data = main_res[0].get('values', [])
        al_data = main_res[1].get('values', [])
        ft_data = main_res[2].get('values', [])
        hol_data = main_res[3].get('values', [])
        md_data = main_res[4].get('values', [])
        pre_data = main_res[5].get('values', [])
        prep_data = main_res[6].get('values', [])
    except Exception:
        rm_data = main_ss.worksheet("routine_master").get_all_values()
        al_data = main_ss.worksheet("activity_log").get_all_values()
        try: ft_data = main_ss.worksheet("future_tasks").get_all_values()
        except: ft_data = []
        try: hol_data = main_ss.worksheet("holidays").get_all_values()
        except: hol_data = []
        try: md_data = main_ss.worksheet("must_do").get_all_values()
        except: md_data = []
        try: pre_data = main_ss.worksheet("PRE").get_all_values()
        except: pre_data = []
        try: prep_data = main_ss.worksheet("prep_checklists").get_all_values()
        except: prep_data = []

    df = process_raw(rm_data, 8, ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App"])
    df = df[df["Day"].astype(str).str.strip() != ""]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()

    log_df = process_raw(al_data, 8, ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])
    log_df = log_df[log_df["Date"].astype(str).str.strip() != ""] 
    log_df["Activity"] = log_df["Activity"].astype(str).str.strip().str.upper()

    future_df = process_raw(ft_data, 8, ["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", "Cancel_Reason"])
    future_df = future_df[future_df["Due_Date"].astype(str).str.strip() != ""] 
    future_df['row_index'] = future_df.index + 2 

    holidays_df = process_raw(hol_data, 2, ["Date", "Occasion"])
    holidays_df = holidays_df[holidays_df["Date"].astype(str).str.strip() != ""] 

    must_do_df = process_raw(md_data, 2, ["Main Category", "Task Name"])
    must_do_df = must_do_df[must_do_df["Main Category"].astype(str).str.strip() != ""] 

    pre_df = process_raw(pre_data, 2, ["Main Category", "Task Name"])
    pre_df = pre_df[pre_df["Main Category"].astype(str).str.strip() != ""] 

    prep_chk_df = process_raw(prep_data, 2, ["Type", "Task Name"])
    prep_chk_df = prep_chk_df[prep_chk_df["Type"].astype(str).str.strip() != ""]

    try:
        money_res = money_ss.values_batch_get(['PAYMENT_CHECKLIST', 'LOCATION_DATA']).get('valueRanges', [])
        pay_data = money_res[0].get('values', [])
        loc_data_vals = money_res[1].get('values', [])
    except:
        try: pay_data = money_ss.worksheet("PAYMENT_CHECKLIST").get_all_values()
        except: pay_data = []
        try: loc_data_vals = money_ss.worksheet("LOCATION_DATA").get_all_values()
        except: loc_data_vals = []

    payment_df = process_raw(pay_data, 9, ["Month", "Bill_Name", "Type", "Est_Amount", "Due_Date", "Status", "Fund", "Account", "Actual_Paid"])
    payment_df = payment_df[payment_df["Month"].astype(str).str.strip() != ""] 
    payment_df['row_index'] = payment_df.index + 2

    if loc_data_vals and len(loc_data_vals) > 1:
        headers = loc_data_vals[0]
        max_len = len(headers)
        recs = [r + [""] * (max_len - len(r)) for r in loc_data_vals[1:] if r]
        loc_df = pd.DataFrame([r[:max_len] for r in recs], columns=headers)
    else:
        loc_df = pd.DataFrame()

    return df, log_df, future_df, holidays_df, payment_df, must_do_df, pre_df, loc_df, prep_chk_df

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

# ==========================================
# Main Logic
# ==========================================
try:
    df, log_df, future_df, holidays_df, payment_df, must_do_df, pre_df, loc_df, prep_chk_df = get_all_ecosystem_data()

    log_df_len = len(log_df)
    future_df_len = len(future_df)

    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    clean_now = now.replace(second=0, microsecond=0).time()
    
    current_day = now.strftime('%A')
    today_str = now.strftime('%Y-%m-%d')
    current_time = now.time()

    return_predef = prep_chk_df[prep_chk_df['Type'].str.strip().str.upper() == 'PREPARE AFTER RETURN BACK HOME']['Task Name'].tolist()
    return_predef = [str(x).strip() for x in return_predef if str(x).strip()]
    
    out_predef = prep_chk_df[prep_chk_df['Type'].str.strip().str.upper() == 'PREPARE BEFORE OUT FROM HOME']['Task Name'].tolist()
    out_predef = [str(x).strip() for x in out_predef if str(x).strip()]

    # ==========================================
    # --- AUTO-LOGGER FOR FULL JOURNEY ---
    # ==========================================
    try:
        if not loc_df.empty and 'Place' in loc_df.columns:
            recent_locs = loc_df.tail(150).copy()
            if 'Date' in recent_locs.columns: recent_locs['Parsed_Date'] = pd.to_datetime(recent_locs['Date'], dayfirst=True, errors='coerce').dt.date
            else: recent_locs['Parsed_Date'] = now.date()
                
            outings = []
            preps_before_out = []
            preps_after_return = []
            
            prev_state = None
            last_dep_time = None
            last_dep_date = None
            
            for _, r in recent_locs.iterrows():
                place = str(r.get('Place', '')).strip().upper()
                status = ""
                for col in ['Type', 'Status', 'Movement', 'Activity']:
                    if col in recent_locs.columns:
                        val = str(r[col]).strip().upper()
                        if val:
                            status = val
                            break
                            
                is_moving = status in ['BIKE', 'WALK', 'TOTO', 'AUTO', 'BUS', 'TRAIN', 'CAR', 'IN_VEHICLE', 'ON_BICYCLE', 'ON_FOOT', 'RUNNING']
                if place == 'HOME' and not is_moving: curr_state = 'HOME'
                elif place != 'HOME' or is_moving: curr_state = 'OUT'
                else: curr_state = prev_state
                    
                row_date_obj = r.get('Parsed_Date', pd.NaT)
                row_date = row_date_obj.strftime('%Y-%m-%d') if pd.notna(row_date_obj) else today_str
                
                row_time = str(r.get('Time', r.get('Start_Time', ''))).strip()
                if not row_time: continue
                try: row_time = datetime.strptime(row_time, '%H:%M:%S').strftime('%H:%M')
                except: pass
                try: row_time = datetime.strptime(row_time, '%H:%M').strftime('%H:%M')
                except: pass
                
                if curr_state == 'OUT' and prev_state == 'HOME':
                    last_dep_time = row_time
                    last_dep_date = row_date
                    preps_before_out.append({'date': row_date, 'dep_time': row_time})
                elif curr_state == 'HOME' and prev_state == 'OUT':
                    arr_time = row_time
                    preps_after_return.append({'date': row_date, 'arr_time': arr_time})
                    if last_dep_time:
                        outings.append({'dep_date': last_dep_date, 'dep_time': last_dep_time, 'arr_date': row_date, 'arr_time': arr_time})
                        last_dep_time = None
                prev_state = curr_state

            logs_to_append = []

            for prep in preps_before_out:
                p_date = prep['date']
                p_dep = prep['dep_time']
                day_logs = log_df[log_df['Date'] == p_date]
                already_logged = False
                for _, log_r in day_logs.iterrows():
                    if str(log_r['Sub_Activities']).strip().upper() == 'PREPARE BEFORE OUT FROM HOME':
                        log_end = str(log_r['End_Time']).strip()
                        try: log_end = datetime.strptime(log_end, '%H:%M').strftime('%H:%M')
                        except: pass
                        if log_end == p_dep:
                            already_logged = True
                            break
                if not already_logged:
                    try:
                        dep_dt = datetime.strptime(f"{p_date} {p_dep}", "%Y-%m-%d %H:%M")
                        start_dt = dep_dt - timedelta(minutes=10)
                        logs_to_append.append([p_date, start_dt.strftime('%H:%M'), p_dep, "0:10", "PRE", "Prepare before out from Home", "", "Auto-logged backwards from Location Data"])
                    except: pass

            for out in outings:
                p_date = out['dep_date']
                p_dep = out['dep_time']
                day_logs = log_df[log_df['Date'] == p_date]
                already_logged = False
                for _, log_r in day_logs.iterrows():
                    if str(log_r['Activity']).strip().upper() == 'OUT':
                        log_start = str(log_r['Start_Time']).strip()
                        try: log_start = datetime.strptime(log_start, '%H:%M').strftime('%H:%M')
                        except: pass
                        if log_start == p_dep:
                            already_logged = True
                            break
                if not already_logged:
                    try:
                        dep_dt = datetime.strptime(f"{out['dep_date']} {out['dep_time']}", "%Y-%m-%d %H:%M")
                        arr_dt = datetime.strptime(f"{out['arr_date']} {out['arr_time']}", "%Y-%m-%d %H:%M")
                        dur_mins = int((arr_dt - dep_dt).total_seconds() / 60)
                        if dur_mins > 0:
                            dur_str = f"{dur_mins // 60}:{dur_mins % 60:02d}"
                            logs_to_append.append([out['dep_date'], out['dep_time'], out['arr_time'], dur_str, "OUT", "Outing", "", "Auto-logged from Location Data"])
                    except: pass

            for prep in preps_after_return:
                p_date = prep['date']
                p_arr = prep['arr_time']
                day_logs = log_df[log_df['Date'] == p_date]
                already_logged = False
                for _, log_r in day_logs.iterrows():
                    if str(log_r['Sub_Activities']).strip().upper() == 'PREPARE AFTER RETURN BACK HOME':
                        log_start = str(log_r['Start_Time']).strip()
                        try: log_start = datetime.strptime(log_start, '%H:%M').strftime('%H:%M')
                        except: pass
                        if log_start == p_arr:
                            already_logged = True
                            break
                if not already_logged:
                    is_latest = (prep == preps_after_return[-1])
                    try:
                        arr_dt = datetime.strptime(f"{p_date} {p_arr}", "%Y-%m-%d %H:%M")
                        arr_dt_aware = ist_timezone.localize(arr_dt)
                        mins_since = (now - arr_dt_aware).total_seconds() / 60.0
                        
                        if mins_since >= 10 or not is_latest or p_date != today_str:
                            end_dt = arr_dt + timedelta(minutes=10)
                            logs_to_append.append([p_date, p_arr, end_dt.strftime('%H:%M'), "0:10", "PRE", "Prepare after return back home", "", "Auto-completed from Location Data"])
                        else:
                            main_ss = get_cached_sheet("MY ROUTINE 2026")
                            smart_append_row(main_ss.worksheet("activity_log"), [p_date, p_arr, "RUNNING", GS_FORMULA, "PRE", "Prepare after return back home", "", "Auto-started from Location Data"], log_df_len)
                            get_all_ecosystem_data.clear()
                            st.toast("🏠 Welcome Home! Started your 10m prep timer.")
                            time.sleep(1.0)
                            st.rerun()
                    except: pass

            if logs_to_append:
                main_ss = get_cached_sheet("MY ROUTINE 2026")
                sheet = main_ss.worksheet("activity_log")
                smart_append_multiple(sheet, logs_to_append)
                get_all_ecosystem_data.clear()
                st.rerun()

        running_preps = log_df[(log_df['End_Time'] == 'RUNNING') & (log_df['Sub_Activities'].str.strip().str.upper() == 'PREPARE AFTER RETURN BACK HOME')]
        for idx, p_row in running_preps.iterrows():
            p_start = str(p_row['Start_Time']).strip()
            arr_dt = datetime.strptime(f"{today_str} {p_start}", "%Y-%m-%d %H:%M")
            arr_dt = ist_timezone.localize(arr_dt)
            mins_since = (now - arr_dt).total_seconds() / 60.0
            
            if mins_since >= 10:
                sheet_row = idx + 2
                end_dt = arr_dt + timedelta(minutes=10)
                main_ss = get_cached_sheet("MY ROUTINE 2026")
                log_sheet = main_ss.worksheet("activity_log")
                
                try: log_sheet.update(range_name=f"C{sheet_row}:D{sheet_row}", values=[[end_dt.strftime('%H:%M'), GS_FORMULA]], value_input_option="USER_ENTERED")
                except TypeError: log_sheet.update(f"C{sheet_row}:D{sheet_row}", [[end_dt.strftime('%H:%M'), GS_FORMULA]], value_input_option="USER_ENTERED")
                
                get_all_ecosystem_data.clear()
                st.toast("✅ Auto-saved 10m Home Prep block.")
                time.sleep(1.0)
                st.rerun()

    except Exception as e:
        print(f"Location Sync Error: {e}")

    running_tasks = log_df[log_df['End_Time'] == 'RUNNING']
    active_count = len(running_tasks)

    # --- HOLIDAY LOGIC MOVED UP ---
    holidays_df['Date_dt'] = pd.to_datetime(holidays_df['Date'], dayfirst=True, errors='coerce')
    today_holiday_match = holidays_df[holidays_df['Date_dt'].dt.date == now.date()]
    is_auto_holiday = not today_holiday_match.empty
    auto_occasion = today_holiday_match.iloc[0]['Occasion'] if is_auto_holiday else ""
    effective_day = "Holiday" if is_auto_holiday else current_day

    # ==========================================
    # --- PENDING EDITS AUDIT SCANNER ---
    # ==========================================
    pending_edits = []
    try:
        prep_logs = log_df[log_df['Sub_Activities'].str.strip().str.upper().isin(['PREPARE AFTER RETURN BACK HOME', 'PREPARE BEFORE OUT FROM HOME'])]
        recent_preps = prep_logs.tail(20) 
        
        for idx, p_row in recent_preps.iterrows():
            p_date = str(p_row['Date']).strip()
            p_start_str = str(p_row['Start_Time']).strip()
            try:
                p_start_dt = datetime.strptime(f"{p_date} {p_start_str}", "%Y-%m-%d %H:%M")
                p_end_dt = p_start_dt + timedelta(minutes=10)
            except: continue

            conflict_found = False
            conflict_reasons = []
            earliest_conflict_dt = p_end_dt

            same_day_logs = log_df[log_df['Date'] == p_date]
            for log_idx, log_r in same_day_logs.iterrows():
                if log_idx == idx: continue
                if str(log_r['Sub_Activities']).strip().upper() in ['PREPARE AFTER RETURN BACK HOME', 'PREPARE BEFORE OUT FROM HOME']:
                    continue
                
                log_start_str = str(log_r['Start_Time']).strip()
                log_end_str = str(log_r['End_Time']).strip()
                
                if log_start_str == log_end_str: continue

                try:
                    log_start_dt = datetime.strptime(f"{p_date} {log_start_str}", "%Y-%m-%d %H:%M")
                    if p_start_dt < log_start_dt < p_end_dt:
                        conflict_found = True
                        conflict_reasons.append(f"Started '{str(log_r['Activity']).strip()}' at {log_start_str}")
                        if log_start_dt < earliest_conflict_dt:
                            earliest_conflict_dt = log_start_dt
                except: pass

            if not loc_df.empty and 'Place' in loc_df.columns:
                loc_df_day = loc_df.copy()
                if 'Date' in loc_df_day.columns:
                    loc_df_day['Parsed_Date'] = pd.to_datetime(loc_df_day['Date'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
                    loc_df_day = loc_df_day[loc_df_day['Parsed_Date'] == p_date]
                else:
                    loc_df_day = loc_df_day.tail(100)

                for _, loc_r in loc_df_day.iterrows():
                    loc_place = str(loc_r.get('Place', '')).strip().upper()
                    if loc_place and loc_place != 'HOME':
                        loc_time_str = str(loc_r.get('Time', loc_r.get('Start_Time', ''))).strip()
                        try:
                            try: loc_time_str = datetime.strptime(loc_time_str, '%H:%M:%S').strftime('%H:%M')
                            except: pass
                            try: loc_time_str = datetime.strptime(loc_time_str, '%H:%M').strftime('%H:%M')
                            except: pass
                            
                            loc_time_dt = datetime.strptime(f"{p_date} {loc_time_str}", "%Y-%m-%d %H:%M")
                            if p_start_dt < loc_time_dt < p_end_dt:
                                conflict_found = True
                                conflict_reasons.append(f"Left for '{loc_r.get('Place', '')}' at {loc_time_str}")
                                if loc_time_dt < earliest_conflict_dt:
                                    earliest_conflict_dt = loc_time_dt
                        except: pass

            if conflict_found:
                actual_end_str = str(p_row['End_Time']).strip()
                needs_edit = False
                if actual_end_str == 'RUNNING': needs_edit = True
                else:
                    try:
                        actual_end_dt = datetime.strptime(f"{p_date} {actual_end_str}", "%Y-%m-%d %H:%M")
                        if actual_end_dt > earliest_conflict_dt: needs_edit = True
                    except: pass

                if needs_edit:
                    pending_edits.append({
                        'sheet_row': idx + 2, 
                        'date': p_date,
                        'start': p_start_str,
                        'reasons': ", ".join(conflict_reasons),
                        'suggested_end': earliest_conflict_dt.strftime('%H:%M')
                    })
    except Exception as e:
        pass

    # ==========================================
    # --- ROUTINE HUB UI HEADER ---
    # ==========================================
    if active_count > 0:
        st.markdown(f'<div style="position: fixed; bottom: 30px; left: 20px; background-color: #ff4b4b; color: white; padding: 8px 16px; border-radius: 20px; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); font-weight: bold; font-size: 16px; z-index: 9999; pointer-events: none; display: flex; align-items: center; justify-content: center;"><span style="font-size: 16px; margin-right: 6px; animation: pulse 1.5s infinite;">⏱️</span> {active_count}</div>', unsafe_allow_html=True)

    st.markdown(f'<h3 style="text-align: center; color: #888; margin-top: 0px; margin-bottom: 0px;">{current_day} | {now.strftime("%I:%M %p")}</h3>', unsafe_allow_html=True)
    
    if is_auto_holiday: 
        st.markdown(f'<p style="text-align: center; color: #ff9f36; font-weight: bold; font-size: 1.1rem; margin-top: 0px;">🎉 {auto_occasion} (Holiday Schedule)</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([8, 2])
    with col2:
        if st.button("🔄 Sync", use_container_width=True):
            get_all_ecosystem_data.clear()
            st.toast("✅ Force Synced with Google Sheets!")
            time.sleep(1.0)
            st.rerun()

    if pending_edits:
        with st.expander(f"⚠️ Action Required: Pending Sheet Edits ({len(pending_edits)})", expanded=True):
            st.markdown("<p style='font-size:13px; color:#666; margin-top:-10px;'>You started a task or left home before your 10m prep finished. Click Auto-Fix to perfectly align the times!</p>", unsafe_allow_html=True)
            for edit in pending_edits:
                st.markdown(f"<div style='background-color:#fff4f4; border-left:4px solid #d32f2f; padding:8px; margin-bottom:5px; font-size:14px;'><b>{edit['date']} at {edit['start']}</b><br><span style='color:#555;'>Conflict: {edit['reasons']}</span></div>", unsafe_allow_html=True)
                if st.button(f"🔧 Auto-Fix to {edit['suggested_end']}", key=f"fix_{edit['sheet_row']}", use_container_width=True):
                    main_ss = get_cached_sheet("MY ROUTINE 2026")
                    log_sheet = main_ss.worksheet("activity_log")
                    
                    try: log_sheet.update(range_name=f"C{edit['sheet_row']}:D{edit['sheet_row']}", values=[[edit['suggested_end'], GS_FORMULA]], value_input_option="USER_ENTERED")
                    except TypeError: log_sheet.update(f"C{edit['sheet_row']}:D{edit['sheet_row']}", [[edit['suggested_end'], GS_FORMULA]], value_input_option="USER_ENTERED")
                    
                    get_all_ecosystem_data.clear()
                    st.toast(f"✅ Fixed! End time perfectly adjusted to {edit['suggested_end']}.")
                    time.sleep(1.0)
                    st.rerun()
            st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

    app_groups = {
        "MONEY": [("Money & Location", "money_location.py", "📍"), ("Money Utilities", "money_utilities.py", "💳"), ("Money Tracker", "money_tracker.py", "💵")],
        "ROUTINE": [("Live Routine Hub", "routine_app.py", "⏱️"), ("Routine Audit", "routine_audit.py", "🔍"), ("Routine Editor", "routine_editor.py", "✏️"), ("Project App", "project_app.py", "🚀")],
        "HEALTH": [("Health Hub", "health_app.py", "❤️"), ("Sleep & Water", "sleep_water_app.py", "💧")],
        "SCH WORK": [("MDM Returns", "mdm_return_log.py", "📦"), ("Video Manager", "bps_ytfb_videos.py", "🎬")],
        "HOME": [("Trace Inventory", "trace.py", "🏷️"), ("Monthly Tracker", "monthly_app.py", "📆")],
        "HARDWARE": [("Backup Tracker", "backup_tracker_app.py", "💾")],
        "BALANCE": [("Strong Tracker", "strong.py", "💪")],
        "ONES": [("Election Duty", "election_duty.py", "🗳️")]
    }
    
    base_app_list = [app for group in app_groups.values() for app in group]

    scheduled_activity = "FREE TIME"
    scheduled_activity_start = None
    next_activity = "NONE"
    next_time_str = ""
    scheduled_sub_activities = ""
    scheduled_check_list = ""
    active_apps_filter = []

    today_schedule = df[df['Day'].str.strip().str.title() == effective_day.title()].to_dict('records')

    for i, row in enumerate(today_schedule):
        try:
            start_str = str(row['Start_Time']).strip()
            end_str = str(row['End_Time']).strip()
            start_t = datetime.strptime(start_str, '%H:%M').time()
            end_t = datetime.strptime('23:59:59', '%H:%M:%S').time() if end_str in ['0:00', '00:00', '24:00'] else datetime.strptime(end_str, '%H:%M').time()

            is_current = (start_t <= current_time <= end_t) if start_t <= end_t else (current_time >= start_t or current_time <= end_t)

            if is_current:
                scheduled_activity = str(row['Activity']).strip().upper()
                scheduled_activity_start = start_t
                scheduled_sub_activities = str(row.get('Sub_Activities', '')).strip()
                scheduled_check_list = str(row.get('check_list', '')).strip()
                
                apps_raw = str(row.get('App', '')).split(',')
                active_apps_filter.extend([a.strip() for a in apps_raw if a.strip()])
                
                if i + 1 < len(today_schedule):
                    next_row = today_schedule[i+1]
                    next_activity = str(next_row['Activity']).strip().upper()
                    next_time_str = datetime.strptime(str(next_row['Start_Time']).strip(), '%H:%M').strftime('%I:%M %p')
                else: next_activity = "END OF DAY"
                break
            elif current_time < start_t and scheduled_activity == "FREE TIME":
                next_activity = str(row['Activity']).strip().upper()
                next_time_str = datetime.strptime(start_str, '%H:%M').strftime('%I:%M %p')
                break
        except ValueError: continue

    current_activity = scheduled_activity
    current_activity_start = scheduled_activity_start
    current_sub_activities = scheduled_sub_activities
    current_check_list = scheduled_check_list

    is_prep_running = any(running_tasks['Sub_Activities'].str.strip().str.upper() == 'PREPARE AFTER RETURN BACK HOME')
    if is_prep_running:
        current_activity = "Welcome Home"
        prep_row = running_tasks[running_tasks['Sub_Activities'].str.strip().str.upper() == 'PREPARE AFTER RETURN BACK HOME'].iloc[0]
        try: current_activity_start = datetime.strptime(str(prep_row['Start_Time']).strip(), '%H:%M').time()
        except: pass

    if current_activity in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY", "PEOPLE"]: color = "#ff4b4b" 
    elif current_activity in ["WORK", "REPORT", "TASK", "HOME TASK", "HOME UTILITIES"]: color = "#0068c9" 
    elif current_activity == "HEALTH": color = "#2e7b32" 
    elif current_activity in ["SLEEP", "PRE", "TEA", "OUT", "PREPARE AFTER RETURN BACK HOME", "Welcome Home"]: color = "#ff9f36" 
    else: color = "#333333" 

    hide_extras = (current_activity == "SLEEP")
    filtered_app_list = [app for app in base_app_list if app[0] in active_apps_filter] if active_apps_filter else []

    if filtered_app_list and not hide_extras:
        st.markdown('<h4 style="text-align: left; color: #d84315; margin-top: 10px;">🚀 Scheduled Apps</h4>', unsafe_allow_html=True)
        for i in range(0, len(filtered_app_list), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(filtered_app_list):
                    app_name, file_name, icon = filtered_app_list[i + j]
                    with cols[j]:
                        if st.button(f"{icon} {app_name}", key=f"sch_app_{i+j}", use_container_width=True):
                            if file_name != "routine_app.py":
                                st.switch_page(file_name)
        st.markdown("---")

    st.markdown(f'<h3 style="margin: 5px 0px 10px 0px; font-size: 1.8rem; color: {color}; letter-spacing: 0.5px; text-align: left;">{current_activity}</h3>', unsafe_allow_html=True)

    if current_activity_start:
        dt_start = datetime.combine(now.date(), current_activity_start)
        dt_start = ist_timezone.localize(dt_start)
        if current_time < current_activity_start: dt_start -= timedelta(days=1)
        elapsed = now - dt_start
        eh, erem = divmod(int(elapsed.total_seconds()), 3600)
        em = erem // 60
        elapsed_text = f"{eh}h {em}m" if eh > 0 else f"{em}m"
        st.markdown(f'<h3 style="text-align: left; color: #555; margin-top: 0px; margin-bottom: 10px; font-weight: 400; font-size: 1.1rem;">⏱️ Elapsed: {elapsed_text}</h3>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="margin-bottom: 15px;"></div>', unsafe_allow_html=True)
        
    if next_activity not in ["NONE", "END OF DAY"]: st.markdown(f'<h4 style="text-align: right; color: #666; margin-bottom: 20px; font-weight: 400; font-size: 1.1rem;">Up Next: <b>{next_activity}</b> at {next_time_str}</h4>', unsafe_allow_html=True)
    elif next_activity == "END OF DAY": st.markdown('<h4 style="text-align: right; color: #666; margin-bottom: 20px; font-weight: 400; font-size: 1.1rem;">Up Next: Schedule Complete</h4>', unsafe_allow_html=True)


    if not hide_extras:
        all_alert_pays = []
        if not payment_df.empty:
            def parse_pay_date(d_str):
                try: return pd.to_datetime(str(d_str).strip(), dayfirst=True).date()
                except: return pd.NaT
            payment_df['Due_Date_dt'] = payment_df['Due_Date'].apply(parse_pay_date)
            pending_payments = payment_df[~payment_df['Status'].str.strip().str.upper().isin(['PAID', 'DONE'])]
            for _, p_row in pending_payments.iterrows():
                if pd.notna(p_row['Due_Date_dt']):
                    days_until = (p_row['Due_Date_dt'] - now.date()).days
                    if days_until <= 3: all_alert_pays.append((days_until, p_row))

        if all_alert_pays:
            all_alert_pays.sort(key=lambda x: x[0])
            min_days = all_alert_pays[0][0]
            if min_days < 0: header_text = f"🔴 OVERDUE PAYMENTS! ({len(all_alert_pays)})"
            elif min_days == 0: header_text = f"🔴 PAYMENTS DUE TODAY! ({len(all_alert_pays)})"
            elif min_days == 1: header_text = f"🟠 Payments Due Tomorrow ({len(all_alert_pays)})"
            else: header_text = f"🟡 Payments Due in {min_days} Days ({len(all_alert_pays)})"
            
            with st.expander(header_text, expanded=False):
                for i, (days_until, p_row) in enumerate(all_alert_pays):
                    if days_until < 0: day_str, item_bg = f"Overdue by {abs(days_until)} days!", "#d32f2f"
                    elif days_until == 0: day_str, item_bg = "Due Today!", "#ef5350"
                    elif days_until == 1: day_str, item_bg = "Due Tomorrow!", "#f57c00"
                    else: day_str, item_bg = f"Due in {days_until} days", "#ffb300"
                    
                    pad_bot = "margin-bottom: 8px;"
                    st.markdown(f'<div style="background-color: {item_bg}; color: white; padding: 8px 12px; border-radius: 6px; {pad_bot} box-shadow: 0 1px 3px rgba(0,0,0,0.1);"><strong style="font-size: 15px;">{p_row["Bill_Name"]} - {day_str}</strong></div>', unsafe_allow_html=True)
                st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

        # --- DYNAMIC CHECKLIST INJECTION ---
        sub_list = [s.strip() for s in current_sub_activities.split(',') if s.strip()]
        chk_list = [c.strip() for c in current_check_list.split(',') if c.strip()]
        all_logged_items = log_df['check_list'].tolist() + log_df['Sub_Activities'].tolist()
        
        running_subs_upper_for_chk = [str(x).strip().upper() for x in running_tasks['Sub_Activities'].tolist()]
        if 'PREPARE AFTER RETURN BACK HOME' in running_subs_upper_for_chk:
            for item in return_predef:
                if item not in chk_list: chk_list.append(item)
        if 'PREPARE BEFORE OUT FROM HOME' in running_subs_upper_for_chk:
            for item in out_predef:
                if item not in chk_list: chk_list.append(item)
        
        if not hide_extras:
            upcoming_ui_elements_raw = []
            if not future_df.empty:
                for _, r in future_df.iterrows():
                    try:
                        due_dt_str = f"{r['Due_Date']} {r['Due_Time']}"
                        due_dt = ist_timezone.localize(datetime.strptime(due_dt_str, "%Y-%m-%d %H:%M"))
                        time_diff = due_dt - now
                        hours_until_due = time_diff.total_seconds() / 3600
                        formatted_task = f"{r['Task_Name']} [Due: {r['Due_Date'][5:]} {r['Due_Time']}]"
                        
                        if str(r['Status']).strip().upper() in ['COMPLETED', 'CANCELED'] or any(formatted_task.upper() == str(x).strip().upper() for x in all_logged_items): continue
                            
                        if hours_until_due <= 24:
                            sec_diff = time_diff.total_seconds()
                            is_overdue = sec_diff < 0
                            abs_sec = abs(int(sec_diff))
                            
                            d, h_rem = divmod(abs_sec, 86400)
                            h, m_rem = divmod(h_rem, 3600)
                            m = m_rem // 60
                            time_parts = []
                            if d > 0: time_parts.append(f"{int(d)}d")
                            if h > 0 or d > 0: time_parts.append(f"{int(h)}h")
                            time_parts.append(f"{int(m)}m")
                            time_str = " ".join(time_parts)
                            
                            time_text = f"Overdue by {time_str}" if is_overdue else f"Due in {time_str}"
                            upcoming_ui_elements_raw.append((due_dt, r, time_text, is_overdue))
                            
                        if hours_until_due <= 0 and str(r['Activity']).strip().upper() == current_activity:
                            if r['Type'] == 'Sub-Activity': sub_list.append(formatted_task)
                            elif r['Type'] == 'Checklist': chk_list.append(formatted_task)
                    except: continue

            if upcoming_ui_elements_raw:
                upcoming_ui_elements_raw.sort(key=lambda x: x[0])
                most_urgent_dt = upcoming_ui_elements_raw[0][0]
                is_urgent_overdue = (most_urgent_dt - now).total_seconds() < 0
                header_text = f"🔴 Upcoming Special Tasks - OVERDUE ({len(upcoming_ui_elements_raw)})" if is_urgent_overdue else f"🟠 Upcoming Special Tasks ({len(upcoming_ui_elements_raw)})"
                
                with st.expander(header_text, expanded=False):
                    for idx_task, (dt, r, time_text, is_overdue) in enumerate(upcoming_ui_elements_raw):
                        item_bg = "#d32f2f" if is_overdue else "#0068c9" 
                        st.markdown(f'<div style="background-color: {item_bg}; color: white; padding: 12px; border-radius: 6px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"><strong style="font-size: 16px;">{r["Task_Name"]} ({r["Activity"]})</strong><br><span style="font-size: 14px; opacity: 0.95;">{time_text}</span></div>', unsafe_allow_html=True)
                        
                        col_run, col_manage = st.columns(2)
                        with col_run:
                            if st.button("▶️ Run Task", key=f"run_sp_{r['row_index']}", use_container_width=True):
                                main_ss = get_cached_sheet("MY ROUTINE 2026")
                                smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, str(r['Activity']).upper(), str(r['Task_Name']).strip(), "", "Started from Special Tasks"], log_df_len)
                                get_all_ecosystem_data.clear() 
                                st.rerun()
                        with col_manage:
                            with st.expander(f"✏️ Manage", expanded=False):
                                tab_resched, tab_cancel = st.tabs(["📅 Reschedule", "❌ Cancel"])
                                with tab_resched:
                                    col_d, col_t = st.columns(2)
                                    try: curr_date = datetime.strptime(str(r['Due_Date']).strip(), '%Y-%m-%d').date()
                                    except: curr_date = now.date()
                                    curr_time_str = str(r['Due_Time']).strip()
                                    time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
                                    if curr_time_str not in time_opts: curr_time_str = "12:00"
                                    
                                    with col_d: new_date = st.date_input("Date", value=curr_date, key=f"nd_{r['row_index']}")
                                    with col_t: new_time = st.selectbox("Time", options=time_opts, index=time_opts.index(curr_time_str), key=f"nt_{r['row_index']}")
                                        
                                    if st.button("Save", key=f"rs_btn_{r['row_index']}", type="primary", use_container_width=True):
                                        main_ss = get_cached_sheet("MY ROUTINE 2026")
                                        fsheet = main_ss.worksheet("future_tasks")
                                        
                                        try: fsheet.update(range_name=f"A{int(r['row_index'])}:B{int(r['row_index'])}", values=[[new_date.strftime('%Y-%m-%d'), new_time]], value_input_option="USER_ENTERED")
                                        except TypeError: fsheet.update(f"A{int(r['row_index'])}:B{int(r['row_index'])}", [[new_date.strftime('%Y-%m-%d'), new_time]], value_input_option="USER_ENTERED")
                                        
                                        smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), GS_FORMULA, str(r['Activity']).upper(), "", f"{r['Task_Name']} [RESCHEDULED]", f"Moved to {new_date.strftime('%Y-%m-%d')} {new_time}"], log_df_len)
                                        get_all_ecosystem_data.clear() 
                                        st.rerun()
                                with tab_cancel:
                                    cancel_reason = st.text_input("Reason", placeholder="Why cancel?", key=f"rsn_{r['row_index']}", label_visibility="collapsed")
                                    if st.button("Confirm", key=f"cnf_{r['row_index']}", type="primary", use_container_width=True):
                                        if cancel_reason.strip():
                                            main_ss = get_cached_sheet("MY ROUTINE 2026")
                                            fsheet = main_ss.worksheet("future_tasks")
                                            
                                            try: fsheet.update(range_name=f"G{int(r['row_index'])}:H{int(r['row_index'])}", values=[["Canceled", cancel_reason]], value_input_option="USER_ENTERED")
                                            except TypeError: fsheet.update(f"G{int(r['row_index'])}:H{int(r['row_index'])}", [["Canceled", cancel_reason]], value_input_option="USER_ENTERED")
                                            
                                            smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), GS_FORMULA, str(r['Activity']).upper(), "", f"{r['Task_Name']} [CANCELED]", f"Cancel Reason: {cancel_reason}"], log_df_len)
                                            get_all_ecosystem_data.clear() 
                                            st.rerun()
                        if idx_task < len(upcoming_ui_elements_raw) - 1: st.markdown('<hr style="margin: 5px 0px 15px 0px; border: 0; border-top: 1px solid #eee;">', unsafe_allow_html=True)
                st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

            future_holidays = holidays_df[holidays_df['Date_dt'].dt.date > now.date()].sort_values('Date_dt')
            if not future_holidays.empty:
                upcoming_hols = future_holidays.head(3)
                with st.expander(f"🌴 Upcoming Holidays ({len(upcoming_hols)})", expanded=False):
                    for _, h_row in upcoming_hols.iterrows():
                        days_until = (h_row['Date_dt'].date() - now.date()).days
                        day_str = "Tomorrow!" if days_until == 1 else f"in {days_until} days"
                        st.markdown(f"**{h_row['Date_dt'].strftime('%b %d, %Y')}** - {h_row['Occasion']} *( {day_str} )*")

            if not pre_df.empty:
                valid_pres = pre_df[pre_df['Task Name'].str.strip() != '']
                if not valid_pres.empty:
                    with st.expander(f"🌅 PRE ({len(valid_pres)})", expanded=False):
                        st.markdown('<p style="text-align: center; color: #888; font-size: 13px; margin-top:-10px;">Tap to start tracking</p>', unsafe_allow_html=True)
                        pre_cols = st.columns(2)
                        running_subs_upper = [str(x).strip().upper() for x in running_tasks['Sub_Activities'].tolist()]
                        for idx, row in valid_pres.iterrows():
                            p_task = str(row['Task Name']).strip()
                            p_cat = str(row['Main Category']).strip().upper() or "PRE"
                            
                            today_logs = log_df[(log_df['Date'] == today_str) & (log_df['Sub_Activities'].str.strip().str.upper() == p_task.upper())]
                            total_mins = 0
                            for _, r in today_logs.iterrows():
                                if r['End_Time'] == 'RUNNING':
                                    try:
                                        r_start = datetime.strptime(f"{r['Date']} {r['Start_Time']}", "%Y-%m-%d %H:%M")
                                        r_start_aware = ist_timezone.localize(r_start)
                                        total_mins += int((now - r_start_aware).total_seconds() // 60)
                                    except: pass
                                else:
                                    try:
                                        dur_val = str(r['Duration']).strip()
                                        if ':' in dur_val:
                                            h_val, m_val = map(int, dur_val.split(':'))
                                            total_mins += h_val * 60 + m_val
                                    except: pass
                                    
                            dur_str = ""
                            if total_mins > 0:
                                d_h, d_m = divmod(total_mins, 60)
                                if d_h > 0 and d_m > 0: dur_str = f" ({d_h}h {d_m}m)"
                                elif d_h > 0: dur_str = f" ({d_h}h)"
                                else: dur_str = f" ({d_m}m)"
                            
                            with pre_cols[idx % 2]:
                                if p_task.upper() in running_subs_upper:
                                    st.button(f"⏳ {p_task}{dur_str}", key=f"pre_run_{idx}", disabled=True, use_container_width=True)
                                elif st.button(f"▶️ {p_task}{dur_str}", key=f"pre_btn_{idx}", use_container_width=True):
                                    main_ss = get_cached_sheet("MY ROUTINE 2026")
                                    smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, p_cat, p_task, "", "PRE Task"], log_df_len)
                                    get_all_ecosystem_data.clear()
                                    st.rerun()

            if not must_do_df.empty:
                valid_must_dos = must_do_df[must_do_df['Task Name'].str.strip() != '']
                if not valid_must_dos.empty:
                    with st.expander(f"⭐ Must Do Tasks ({len(valid_must_dos)})", expanded=False):
                        st.markdown('<p style="text-align: center; color: #888; font-size: 13px; margin-top:-10px;">Tap to start tracking</p>', unsafe_allow_html=True)
                        md_cols = st.columns(2)
                        running_subs_upper = [str(x).strip().upper() for x in running_tasks['Sub_Activities'].tolist()]
                        for idx, row in valid_must_dos.iterrows():
                            md_task = str(row['Task Name']).strip()
                            md_cat = str(row['Main Category']).strip().upper() or "WORK"
                            
                            today_logs = log_df[(log_df['Date'] == today_str) & (log_df['Sub_Activities'].str.strip().str.upper() == md_task.upper())]
                            total_mins = 0
                            for _, r in today_logs.iterrows():
                                if r['End_Time'] == 'RUNNING':
                                    try:
                                        r_start = datetime.strptime(f"{r['Date']} {r['Start_Time']}", "%Y-%m-%d %H:%M")
                                        r_start_aware = ist_timezone.localize(r_start)
                                        total_mins += int((now - r_start_aware).total_seconds() // 60)
                                    except: pass
                                else:
                                    try:
                                        dur_val = str(r['Duration']).strip()
                                        if ':' in dur_val:
                                            h_val, m_val = map(int, dur_val.split(':'))
                                            total_mins += h_val * 60 + m_val
                                    except: pass
                                    
                            dur_str = ""
                            if total_mins > 0:
                                d_h, d_m = divmod(total_mins, 60)
                                if d_h > 0 and d_m > 0: dur_str = f" ({d_h}h {d_m}m)"
                                elif d_h > 0: dur_str = f" ({d_h}h)"
                                else: dur_str = f" ({d_m}m)"
                            
                            with md_cols[idx % 2]:
                                if total_mins > 0:
                                    st.markdown(f'''
                                        <div id="md_green_{idx}"></div>
                                        <style>
                                        div.element-container:has(#md_green_{idx}) + div.element-container button {{
                                            background-color: #e8f5e9 !important;
                                            border: 1px solid #81c784 !important;
                                            color: #1b5e20 !important;
                                            font-weight: 600 !important;
                                        }}
                                        </style>
                                    ''', unsafe_allow_html=True)

                                if md_task.upper() in running_subs_upper:
                                    st.button(f"⏳ {md_task}{dur_str}", key=f"md_run_{idx}", disabled=True, use_container_width=True)
                                elif st.button(f"▶️ {md_task}{dur_str}", key=f"md_btn_{idx}", use_container_width=True):
                                    main_ss = get_cached_sheet("MY ROUTINE 2026")
                                    smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, md_cat, md_task, "", "Must Do Task"], log_df_len)
                                    get_all_ecosystem_data.clear()
                                    st.rerun()

            if chk_list:
                with st.expander(f"✅ Tasks & Reminders ({len(chk_list)})", expanded=True):
                    today_logs = log_df[log_df['Date'] == today_str]
                    today_logged_tasks = today_logs[today_logs['Activity'].isin([current_activity, 'PRE'])]['check_list'].tolist()
                    
                    for task in chk_list:
                        is_done = any(task.upper() == str(x).strip().upper() for x in (all_logged_items if "[Due:" in task else today_logged_tasks))
                        if "[Due:" in task and not is_done:
                            raw_task = task.split(" [Due:")[0].strip()
                            matches = future_df[(future_df['Task_Name'].str.strip() == raw_task) & (future_df['Type'] == 'Checklist')]
                            if not matches.empty and str(matches.iloc[0]['Status']).strip().upper() in ['COMPLETED', 'CANCELED']: is_done = True
                        
                        checked = st.checkbox(f"{task} (Last: {get_last_done_str(task, log_df, now, col_name='check_list')})", value=is_done, disabled=is_done, key=f"chk_{task}_{current_activity}")
                        if checked and not is_done:
                            log_act = "PRE" if task in (return_predef + out_predef) else current_activity
                            main_ss = get_cached_sheet("MY ROUTINE 2026")
                            smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), now.strftime('%H:%M'), GS_FORMULA, log_act, "", task, "Checked off"], log_df_len)
                            if "[Due:" in task:
                                matches = future_df[(future_df['Task_Name'].str.strip() == task.split(" [Due:")[0].strip()) & (future_df['Type'] == 'Checklist')]
                                if not matches.empty:
                                    main_ss.worksheet("future_tasks").update_cell(int(matches.iloc[0]['row_index']), 7, "Completed") 
                            get_all_ecosystem_data.clear() 
                            st.rerun()

        if sub_list or active_count > 0:
            st.markdown("---")
            st.markdown('<h4 style="text-align: center; color: #333;">Tap to Track Activity</h4>', unsafe_allow_html=True)
            
            if active_count > 0:
                for idx, active_row in running_tasks.iterrows():
                    sheet_row = idx + 2 
                    display_name = str(active_row['Sub_Activities']) or str(active_row['Activity'])
                    is_home_prep = (str(active_row['Sub_Activities']).strip().upper() == 'PREPARE AFTER RETURN BACK HOME')
                    
                    try:
                        dt_naive = datetime.strptime(f"{active_row['Date']} {active_row['Start_Time']}", "%Y-%m-%d %H:%M")
                        mins_elapsed = int((now - ist_timezone.localize(dt_naive)).total_seconds() // 60)
                    except: mins_elapsed = 0 
                    
                    cycle_minute = mins_elapsed % 30
                    pomodoro_count = (mins_elapsed // 30) + 1
                    current_state = "Focus" if cycle_minute < 25 else "Break"
                    task_id = f"task_{sheet_row}"
                    
                    if task_id in st.session_state.pomodoro_state and st.session_state.pomodoro_state[task_id] != current_state:
                        components.html("""<script>try {var ctx = new (window.AudioContext || window.webkitAudioContext)();function playBeep(freq, time, dur) {var osc = ctx.createOscillator();var gain = ctx.createGain();osc.connect(gain);gain.connect(ctx.destination);osc.frequency.value = freq;osc.type = "square";gain.gain.setValueAtTime(0.1, time);gain.gain.exponentialRampToValueAtTime(0.001, time + dur);osc.start(time);osc.stop(time + dur);}playBeep(600, ctx.currentTime, 0.2);playBeep(800, ctx.currentTime + 0.2, 0.3);} catch(e) {}</script>""", height=0, width=0)
                    st.session_state.pomodoro_state[task_id] = current_state

                    p_color, p_state, p_left, p_prog = ("#d84315", "🍅 Focus Time", 25 - cycle_minute, cycle_minute / 25.0) if current_state == "Focus" else ("#2e7b32", "☕ Break Time", 30 - cycle_minute, (cycle_minute - 25) / 5.0)
                    
                    dur_str_running = ""
                    if mins_elapsed > 0:
                        d_h, d_m = divmod(mins_elapsed, 60)
                        if d_h > 0 and d_m > 0: dur_str_running = f"{d_h}h {d_m}m"
                        elif d_h > 0: dur_str_running = f"{d_h}h"
                        else: dur_str_running = f"{d_m}m"
                    else: dur_str_running = "0m"

                    st.markdown(f'<div style="background-color: #f8f9fa; border-left: 5px solid {p_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"><div style="display: flex; justify-content: space-between; align-items: center;"><strong style="font-size: 16px; color: #333;">⏳ {display_name}</strong><span style="color: #666; font-size: 14px;">Total: {dur_str_running}</span></div><div style="margin-top: 8px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;"><span style="color: {p_color}; font-weight: bold; font-size: 14px;">{p_state} (Cycle {pomodoro_count})</span><span style="color: #555; font-size: 13px; font-weight: bold;">{p_left}m left</span></div><div style="width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 6px;"><div style="width: {p_prog * 100}%; background-color: {p_color}; height: 6px; border-radius: 4px; transition: width 0.5s ease;"></div></div></div>', unsafe_allow_html=True)

                    if is_home_prep:
                        mins_remaining = max(0, 10 - mins_elapsed)
                        st.markdown(f"<div style='text-align:center; color:#888; font-size:13px; margin-bottom:5px; font-weight:bold;'><i>⏳ This timer will automatically close in {mins_remaining} minutes.</i></div>", unsafe_allow_html=True)
                        st.markdown("<div style='text-align:center; color:#d84315; font-size:11px; margin-bottom:15px;'><i>📝 Note: Auto-Fix your sheet above if you start a new activity before this finishes!</i></div>", unsafe_allow_html=True)
                    else:
                        col_stop, col_cancel = st.columns(2)
                        with col_stop:
                            if st.button("🛑 SAVE", key=f"save_{sheet_row}", use_container_width=True, type="primary"):
                                main_ss = get_cached_sheet("MY ROUTINE 2026")
                                log_sheet = main_ss.worksheet("activity_log")
                                
                                try: log_sheet.update(range_name=f"C{sheet_row}:D{sheet_row}", values=[[now.strftime('%H:%M'), GS_FORMULA]], value_input_option="USER_ENTERED")
                                except TypeError: log_sheet.update(f"C{sheet_row}:D{sheet_row}", [[now.strftime('%H:%M'), GS_FORMULA]], value_input_option="USER_ENTERED")
                                
                                if str(active_row['Notes']).strip() == "": log_sheet.update_cell(sheet_row, 8, "Auto-logged via Timer") 
                                    
                                if "[Due:" in str(active_row['Sub_Activities']):
                                    matches = future_df[(future_df['Task_Name'].str.strip() == str(active_row['Sub_Activities']).split(" [Due:")[0].strip()) & (future_df['Type'] == 'Sub-Activity')]
                                    if not matches.empty:
                                        main_ss.worksheet("future_tasks").update_cell(int(matches.iloc[0]['row_index']), 7, "Completed") 
                                get_all_ecosystem_data.clear() 
                                st.rerun()

                        with col_cancel:
                            if st.button("❌ CANCEL", key=f"cancel_{sheet_row}", use_container_width=True):
                                main_ss = get_cached_sheet("MY ROUTINE 2026")
                                main_ss.worksheet("activity_log").delete_rows(sheet_row)
                                get_all_ecosystem_data.clear() 
                                st.rerun()
            
            avail_subs = [t for t in sub_list if t not in running_tasks['Sub_Activities'].tolist()]
            if avail_subs:
                st.markdown('<div style="margin-top: 15px; margin-bottom: 5px; color: #333;"><b>▶️ Routine Tasks:</b></div>', unsafe_allow_html=True)
                
                for i in range(0, len(avail_subs), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(avail_subs):
                            task = avail_subs[i+j]
                            with cols[j]:
                                if st.button(f"▶️ {task}" + ("" if "[Due:" in task else f"\n(Last: {get_last_done_str(task, log_df, now, col_name='Sub_Activities')})"), key=f"btn_{i+j}_{task}", use_container_width=True):
                                    main_ss = get_cached_sheet("MY ROUTINE 2026")
                                    smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, current_activity, task, "", "Auto-logged via Timer"], log_df_len)
                                    get_all_ecosystem_data.clear() 
                                    st.rerun()

    if not hide_extras:
        st.markdown("""
            <style>
            div[data-testid="stForm"]:has(.visitor-anchor) {
                background-color: #fff4f4 !important;
                border: 1px solid #ffcdd2 !important;
                border-radius: 10px !important;
                padding: 15px !important;
            }
            </style>
        """, unsafe_allow_html=True)

        with st.form("visitor_tracker_form"):
            st.markdown('<span class="visitor-anchor"></span>', unsafe_allow_html=True)
            st.markdown('<div style="color: #ff4b4b; font-size: 18px; margin-bottom: 10px;"><b>👥 Visitor Tracker</b></div>', unsafe_allow_html=True)

            if st.form_submit_button("⚡ Quick Start (Update Details Later)", use_container_width=True):
                main_ss = get_cached_sheet("MY ROUTINE 2026")
                smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "PEOPLE", "VISITOR", "", "Update details later"], log_df_len)
                get_all_ecosystem_data.clear() 
                st.rerun()

            st.markdown("<p style='text-align:center; font-size:12px; color:#888; margin: 12px 0;'>— OR ENTER DETAILS FIRST —</p>", unsafe_allow_html=True)
            
            with st.expander("📝 Enter Details Before Starting", expanded=False):
                col_mt1, col_mt2 = st.columns(2)
                with col_mt1: interaction_type = st.selectbox("Type", ["Attend Visitor", "Meet People"], key="live_mtg_type")
                extracted_names = [(val.split(" - ", 1)[-1].strip() if " - " in val else val.strip()) for val in log_df[log_df['Activity'] == 'PEOPLE']['Sub_Activities'].dropna().astype(str)]
                with col_mt2: person_type = st.selectbox("Person", ["-- New Person --"] + sorted(list(set([n for n in extracted_names if n]))), key="live_mtg_person")
                person_name = st.text_input("Name of New Person", key="live_mtg_new_name") if person_type == "-- New Person --" else person_type
                topic_talk = st.text_input("Topic", key="live_mtg_topic")
                purpose_visit = st.text_input("Purpose", key="live_mtg_purpose")
                
                if st.form_submit_button("▶️ Start with Details", type="primary", use_container_width=True):
                    main_ss = get_cached_sheet("MY ROUTINE 2026")
                    smart_append_row(main_ss.worksheet("activity_log"), [today_str, now.strftime('%H:%M'), "RUNNING", GS_FORMULA, "PEOPLE", f"{interaction_type} - {(person_name.strip() if person_name else 'Unknown')}".upper(), "", f"Topic: {topic_talk} | Purpose: {purpose_visit}"], log_df_len)
                    get_all_ecosystem_data.clear() 
                    st.rerun()

        with st.expander("🗓️ Schedule Future Task"):
            with st.form("schedule_future_form", clear_on_submit=True):
                f_act_list = [act for act in df['Activity'].unique() if act.strip()]
                f_act = st.selectbox("Parent Category", f_act_list, key="f_act")
                f_act_custom = st.text_input("New Parent Category (Leave blank to use selected above)", placeholder="Type custom category here...", key="f_act_custom")
                
                f_type = st.radio("Task Type", ["Checklist", "Sub-Activity"], horizontal=True, key="f_type")
                f_name = st.text_input("Task Details", placeholder="e.g., Pay Electricity Bill", key="f_name")
                time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
                col1, col2 = st.columns(2)
                with col1: f_date = st.date_input("Due Date", value=now.date(), key="f_date")
                with col2: f_time = datetime.strptime(st.selectbox("Due Time", options=time_opts, index=time_opts.index(clean_now.strftime('%H:%M')), key="f_time"), '%H:%M').time()
                    
                if st.form_submit_button("Schedule Task", use_container_width=True):
                    final_act = f_act_custom.strip().upper() if f_act_custom.strip() else f_act.strip().upper()
                    if f_name:
                        main_ss = get_cached_sheet("MY ROUTINE 2026")
                        smart_append_row(main_ss.worksheet("future_tasks"), [f_date.strftime('%Y-%m-%d'), f_time.strftime('%H:%M'), final_act, f_type, f_name.strip(), "Personal", "Pending", ""], future_df_len)
                        get_all_ecosystem_data.clear() 
                        st.rerun()
                    else: st.error("Please enter task details.")

        with st.expander("📝 Manual Log Activity"):
            unique_acts = sorted(list(set([a.strip().upper() for a in df['Activity'] if a.strip()])))
            log_date = st.date_input("Date", value=now.date(), key="log_date")
            
            col_act1, col_act2 = st.columns(2)
            with col_act1: 
                default_act_idx = unique_acts.index(current_activity) + 1 if current_activity in unique_acts else 0
                sel_act = st.selectbox("Activity", ["-- Type Custom --"] + unique_acts, index=default_act_idx, key="sel_act")
                log_activity = st.text_input("Type Custom Activity", key="txt_act") if sel_act == "-- Type Custom --" else sel_act
                
            with col_act2: 
                dependent_subs = []
                if log_activity in unique_acts:
                    filtered_df = df[df['Activity'].str.strip().str.upper() == log_activity]
                    sub_list = []
                    for s in filtered_df['Sub_Activities']:
                        sub_list.extend([x.strip().title() for x in str(s).split(',') if x.strip()])
                    dependent_subs = sorted(list(set(sub_list)))

                sel_sub = st.selectbox("Sub-Activity", ["-- None / Type Custom --"] + dependent_subs, index=0, key="sel_sub")
                log_sub_activity = st.text_input("Type Custom Sub-Activity", key="txt_sub") if sel_sub == "-- None / Type Custom --" else sel_sub
                if sel_sub == "-- None / Type Custom --" and not log_sub_activity: 
                    log_sub_activity = ""
                
            hours = [f"{i:02d}" for i in range(24)]
            minutes = [f"{i:02d}" for i in range(60)]
            curr_h = int(clean_now.strftime('%H'))
            curr_m = int(clean_now.strftime('%M'))
            
            col1, col2 = st.columns(2)
            with col1: 
                st.markdown('<div style="font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #333;">Started At (HH : MM)</div>', unsafe_allow_html=True)
                c_sh, c_sm = st.columns(2)
                s_hour = c_sh.selectbox("Start Hour", hours, index=curr_h, key="s_hour", label_visibility="collapsed")
                s_min = c_sm.selectbox("Start Min", minutes, index=curr_m, key="s_min", label_visibility="collapsed")
                
            with col2: 
                st.markdown('<div style="font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #333;">Ended At (HH : MM)</div>', unsafe_allow_html=True)
                c_eh, c_em = st.columns(2)
                e_hour = c_eh.selectbox("End Hour", hours, index=curr_h, key="e_hour", label_visibility="collapsed")
                e_min = c_em.selectbox("End Min", minutes, index=curr_m, key="e_min", label_visibility="collapsed")
            
            log_chk = st.text_input("Checklist Item (Optional)", key="log_chk")    
            log_notes = st.text_area("Notes", key="log_notes")
            
            if st.button("💾 Save to Activity Log", use_container_width=True, type="primary"):
                if log_activity:
                    main_ss = get_cached_sheet("MY ROUTINE 2026")
                    smart_append_row(main_ss.worksheet("activity_log"), [
                        log_date.strftime('%Y-%m-%d'), 
                        f"{s_hour}:{s_min}", 
                        f"{e_hour}:{e_min}", 
                        GS_FORMULA, 
                        log_activity.upper().strip(), 
                        log_sub_activity.title().strip(), 
                        log_chk.strip(), 
                        log_notes
                    ], log_df_len)
                    get_all_ecosystem_data.clear() 
                    st.success("Activity Logged!")
                    time.sleep(1.0)
                    st.rerun()
                else: 
                    st.error("Please provide an Activity.")

        # --- PERMANENT ALL APPS LAUNCHPAD (At the Bottom) ---
        st.markdown("---")
        with st.expander("🧩 All Applications Launchpad", expanded=not bool(filtered_app_list)):
            for group_name, apps in app_groups.items():
                st.markdown(f"<div style='color: #0068c9; font-weight: bold; margin-top: 10px; margin-bottom: 5px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>{group_name}</div>", unsafe_allow_html=True)
                for i in range(0, len(apps), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(apps):
                            app_name, file_name, icon = apps[i + j]
                            with cols[j]:
                                if st.button(f"{icon} {app_name}", key=f"all_{group_name}_{i+j}", use_container_width=True):
                                    if file_name != "routine_app.py":
                                        st.switch_page(file_name)
                st.markdown("<hr style='margin: 5px 0px 10px 0px; border: 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)

except Exception as e: st.error(f"System Error: {e}")
