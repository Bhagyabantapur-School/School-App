import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("dashboard.py") 
st.write("---") 
# -------------------
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz

st.set_page_config(page_title="Routine Audit", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    div[data-testid="metric-container"] {
        text-align: center; 
        background-color: #f0f2f6; 
        padding: 10px; 
        border-radius: 10px; 
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Database Connection & Caching Helpers
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def get_main_spreadsheet():
    return init_connection().open("MY ROUTINE 2026")

def get_money_spreadsheet():
    return init_connection().open("sk_money_location")

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try: sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
    except TypeError: sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=300)
def get_activity_log():
    data = get_main_spreadsheet().worksheet("activity_log").get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    return df

@st.cache_data(ttl=300)
def get_location_data():
    try: sheet = get_money_spreadsheet().worksheet("LOCATION_DATA")
    except Exception: return pd.DataFrame(columns=["Date", "Time", "Move", "Place", "People", "Remark"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Date", "Time", "Move", "Place", "People", "Remark"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 6: df[df.shape[1]] = ""
    df = df.iloc[:, :6]
    df.columns = ["Date", "Time", "Move", "Place", "People", "Remark"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    return df

@st.cache_data(ttl=300)
def get_visited_places():
    try:
        data = get_money_spreadsheet().worksheet("VISITED_PLACES").get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=["Place", "Purpose"])
        return pd.DataFrame(data[1:], columns=data[0])
    except Exception: return pd.DataFrame(columns=["Place", "Purpose"])

@st.cache_data(ttl=300)
def get_water_log():
    ss = get_main_spreadsheet()
    try: sheet = ss.worksheet("water_log")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="water_log", rows="1000", cols="3")
        smart_append_row(sheet, ["Date", "Time", "Amount_ml"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Date", "Time", "Amount_ml"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 3: df[df.shape[1]] = ""
    df = df.iloc[:, :3]
    df.columns = ["Date", "Time", "Amount_ml"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    df['Amount_ml'] = pd.to_numeric(df['Amount_ml'], errors='coerce').fillna(0)
    return df

def get_short_stop_label(place):
    p = str(place).upper()
    if "HOME" in p: return "🏠 Home Base"
    if "KARIM" in p: return "🔑 Key Drop / Pickup"
    if any(k in p for k in ["FRUIT", "SHOP", "STORE", "MARKET", "MALL"]): return "🛒 Quick Errand"
    if any(k in p for k in ["BUS", "STAND", "STATION", "STOP"]): return "🚏 Transit Wait"
    if any(k in p for k in ["SCHOOL", "MADRASA"]): return "🏫 School / Education"
    return "📍 General Visit"

# ==========================================
# Main App UI
# ==========================================
try:
    log_df = get_activity_log() 
    loc_df = get_location_data() 
    visited_places_df = get_visited_places()
    water_df = get_water_log()
    
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    today_str = now.strftime('%Y-%m-%d')

    st.markdown("<h2 style='text-align: center; color: #555; margin-top: 0px;'>📊 Daily Data & Audit Hub</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["⏳ Timeline Audit", "💧 Hydration", "📍 Places Database"])

    # ==========================================
    # TAB 1: TIMELINE AUDIT
    # ==========================================
    with tab1:
        col_t, col_s = st.columns([8, 2])
        with col_t: st.markdown("<h3 style='color: #555; margin-top: 0px;'>Daily Activity Timeline</h3>", unsafe_allow_html=True)
        with col_s:
            if st.button("🔄 Sync Logs", use_container_width=True):
                get_activity_log.clear()
                get_location_data.clear()
                st.rerun()
                
        selected_timeline_date = st.date_input("Select Date to Review", value=now.date(), key="timeline_date_sel")
        selected_date_str = selected_timeline_date.strftime('%Y-%m-%d')
        formatted_target_date = selected_timeline_date.strftime('%d.%m.%y') 
        prev_date_str = (selected_timeline_date - timedelta(days=1)).strftime('%Y-%m-%d')
        
        def get_gap_label(dur, loc, visited_df, start_dt, end_dt):
            if "HOME" in str(loc).upper(): return get_short_stop_label(loc) if dur < 5 else "Unlogged Time / Break"
            found_purposes = []
            if not visited_df.empty:
                matches = visited_df[visited_df['Place'].str.strip().str.upper() == str(loc).strip().upper()]
                if not matches.empty:
                    if 'Visit Dates & Times' in matches.columns:
                        for _, m_row in matches.iterrows():
                            visit_times_str = str(m_row['Visit Dates & Times'])
                            if pd.notna(visit_times_str) and visit_times_str.strip() != "":
                                for t_str in visit_times_str.split('\n'):
                                    if t_str.strip():
                                        try:
                                            if (start_dt - pd.Timedelta(minutes=1)) <= pd.to_datetime(t_str.strip(), format="%d.%m.%y %H:%M") <= (end_dt + pd.Timedelta(minutes=1)):
                                                if str(m_row['Purpose']).strip() and str(m_row['Purpose']).strip() not in found_purposes: found_purposes.append(str(m_row['Purpose']).strip())
                                        except: pass
                    if found_purposes: return " + ".join(found_purposes)
                    if 'Visit Dates & Times' in matches.columns:
                        for _, m_row in matches.iterrows():
                            if pd.notna(m_row['Visit Dates & Times']) and formatted_target_date in str(m_row['Visit Dates & Times']):
                                if pd.notna(m_row['Purpose']) and str(m_row['Purpose']).strip(): return str(m_row['Purpose']).strip()
                    if pd.notna(matches.iloc[0]['Purpose']) and str(matches.iloc[0]['Purpose']).strip(): return str(matches.iloc[0]['Purpose']).strip()
            return get_short_stop_label(loc) if dur < 5 else "Unlogged Time / Break"
        
        day_logs_raw = log_df[(log_df['Date'].isin([selected_date_str, prev_date_str])) & (log_df['End_Time'] != 'RUNNING')].copy()
        day_start_dt, day_end_dt = pd.to_datetime(selected_date_str + ' 00:00:00'), pd.to_datetime(selected_date_str + ' 23:59:59')
        
        if day_logs_raw.empty: day_logs = pd.DataFrame(columns=['Date', 'Start_Time', 'End_Time', 'Duration', 'Activity', 'Sub_Activities', 'check_list', 'Notes', 'Start_DT', 'End_DT', 'Display_Start', 'Display_End'])
        else:
            day_logs_raw['Start_DT'] = pd.to_datetime(day_logs_raw['Date'] + ' ' + day_logs_raw['Start_Time'], errors='coerce')
            day_logs_raw['End_DT'] = pd.to_datetime(day_logs_raw['Date'] + ' ' + day_logs_raw['End_Time'], errors='coerce')
            mask = day_logs_raw['End_DT'] < day_logs_raw['Start_DT']
            day_logs_raw.loc[mask, 'End_DT'] = day_logs_raw.loc[mask, 'End_DT'] + pd.Timedelta(days=1)
            day_logs = day_logs_raw[(day_logs_raw['End_DT'] > day_start_dt) & (day_logs_raw['Start_DT'] <= day_end_dt)].copy()
            day_logs['Display_Start'], day_logs['Display_End'] = day_logs['Start_DT'].clip(lower=day_start_dt), day_logs['End_DT'].clip(upper=day_end_dt)
            day_logs = day_logs.sort_values('Display_Start').dropna(subset=['Display_Start', 'Display_End'])

        end_marker_dt = pd.to_datetime(now.strftime('%Y-%m-%d %H:%M')) if selected_date_str == today_str else pd.to_datetime(selected_date_str + ' 23:59:00')
        dummy_row = pd.DataFrame([{'Start_DT': end_marker_dt, 'End_DT': end_marker_dt, 'Display_Start': end_marker_dt, 'Display_End': end_marker_dt, 'Activity': 'CURRENT_TIME_MARKER', 'Sub_Activities': '', 'check_list': '', 'Notes': '', 'Date': selected_date_str, 'Start_Time': end_marker_dt.strftime('%H:%M'), 'End_Time': end_marker_dt.strftime('%H:%M'), 'Duration': '0:00'}])
        day_logs = pd.concat([day_logs, dummy_row], ignore_index=True).sort_values('Display_Start')

        loc_df_safe = loc_df.copy()
        def parse_custom_date(date_str):
            try: return datetime.strptime(str(date_str).strip().split(' ')[0], '%d.%m.%y').date()
            except:
                try: return pd.to_datetime(str(date_str).strip(), dayfirst=True).date()
                except: return None

        loc_df_safe['Parsed_Date'] = loc_df_safe['Date'].apply(parse_custom_date)
        day_locs = loc_df_safe[loc_df_safe['Parsed_Date'] == selected_timeline_date].copy()
        
        if not day_locs.empty:
            def parse_custom_dt(row):
                try: return datetime.strptime(f"{str(row['Date']).strip().split(' ')[0]} {str(row['Time']).strip()}", '%d.%m.%y %H:%M')
                except: return pd.NaT
            day_locs['Loc_DT'] = day_locs.apply(parse_custom_dt, axis=1)
            
            def parse_loc_row(row):
                m_raw, p_raw = str(row['Move']).strip(), str(row['Place']).strip()
                if any(k in m_raw.upper() for k in ['BIKE', 'WALK', 'TOTO', 'AUTO', 'BUS', 'CAR', 'TRAIN', 'CYCLE', 'SCOOTER', 'VAN']): return pd.Series([m_raw, p_raw])
                if "- STATIONARY -" in m_raw.upper(): return pd.Series(["- Stationary -", p_raw])
                return pd.Series(["- Stationary -", p_raw]) if p_raw and p_raw.upper() not in ["I", "NAN", "NONE"] else pd.Series(["- Stationary -", m_raw])

            day_locs[['Clean_Move', 'Clean_Place']] = day_locs.apply(parse_loc_row, axis=1)
            day_locs['Move'], day_locs['Place'] = day_locs['Clean_Move'], day_locs['Clean_Place']
            day_locs = day_locs[day_locs.apply(lambda r: str(r['Move']).strip().upper() != "- STATIONARY -" or (len(str(r['Place']).strip()) > 1 and str(r['Place']).strip().upper() not in ["I", "NAN", "NONE"]), axis=1)].dropna(subset=['Loc_DT']).sort_values('Loc_DT')
        
        start_time_limit = pd.to_datetime(selected_date_str + ' 05:00')
        if not day_locs.empty and day_locs['Loc_DT'].min() < start_time_limit: start_time_limit = day_locs['Loc_DT'].min()
        if not day_logs.empty and day_logs.iloc[0]['Display_Start'] < start_time_limit and day_logs.iloc[0]['Activity'] != 'CURRENT_TIME_MARKER': start_time_limit = day_logs.iloc[0]['Display_Start']

        last_end_time = start_time_limit
        timeline_events = []
        
        for _, row in day_logs.iterrows():
            current_start, current_end = row['Display_Start'], row['Display_End']
            
            if last_end_time and current_start > last_end_time:
                gap_duration = (current_start - last_end_time).total_seconds() / 60
                if gap_duration > 0:
                    if gap_duration <= 5: 
                        timeline_events.append({'type': 'transition', 'start': last_end_time.strftime('%I:%M %p'), 'end': current_start.strftime('%I:%M %p'), 'duration': int(gap_duration), 'activity': 'Transition', 'sub': '', 'notes': '', 'place': '', 'move': ''})
                    else: 
                        gap_start_dt, gap_end_dt = last_end_time, current_start
                        locs_in_gap = day_locs[(day_locs['Loc_DT'] > gap_start_dt) & (day_locs['Loc_DT'] < gap_end_dt)] if not day_locs.empty else pd.DataFrame()
                            
                        def get_loc_state_at_time(t):
                            if day_locs.empty: return "", "- Stationary -"
                            past = day_locs[day_locs['Loc_DT'] <= t]
                            return (past.iloc[-1]['Place'], past.iloc[-1]['Move']) if not past.empty else (day_locs.iloc[0]['Place'], day_locs.iloc[0]['Move'])
                            
                        curr_gap_start = gap_start_dt
                        curr_loc, curr_move = get_loc_state_at_time(curr_gap_start)
                        transit_modes = [curr_move] if curr_move.upper() != "- STATIONARY -" else []
                        
                        if locs_in_gap.empty:
                            act_label = f"On the way ({' + '.join(transit_modes)})" if transit_modes else get_gap_label(gap_duration, curr_loc, visited_places_df, gap_start_dt, gap_end_dt)
                            timeline_events.append({'type': 'gap', 'start': gap_start_dt.strftime('%I:%M %p'), 'end': gap_end_dt.strftime('%I:%M %p'), 'duration': int(gap_duration), 'activity': act_label, 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                        else:
                            for _, l_row in locs_in_gap.iterrows():
                                split_time, new_move, new_loc = l_row['Loc_DT'], str(l_row['Move']).strip(), str(l_row['Place']).strip()
                                is_new_stat, is_curr_stat = new_move.upper() == "- STATIONARY -", curr_move.upper() == "- STATIONARY -"
                                
                                if is_new_stat:
                                    if not is_curr_stat:
                                        sub_gap_dur = (split_time - curr_gap_start).total_seconds() / 60
                                        if sub_gap_dur >= 0: timeline_events.append({'type': 'gap', 'start': curr_gap_start.strftime('%I:%M %p'), 'end': split_time.strftime('%I:%M %p'), 'duration': int(sub_gap_dur), 'activity': f"On the way ({' + '.join(transit_modes)})" if transit_modes else "On the way", 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                                        curr_gap_start, curr_loc, curr_move, transit_modes = split_time, new_loc, new_move, []
                                    elif new_loc.upper() != curr_loc.upper() and curr_loc != "":
                                        sub_gap_dur = (split_time - curr_gap_start).total_seconds() / 60
                                        if sub_gap_dur >= 0: timeline_events.append({'type': 'gap', 'start': curr_gap_start.strftime('%I:%M %p'), 'end': split_time.strftime('%I:%M %p'), 'duration': int(sub_gap_dur), 'activity': get_gap_label(sub_gap_dur, curr_loc, visited_places_df, curr_gap_start, split_time), 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                                        curr_gap_start, curr_loc, curr_move = split_time, new_loc, new_move
                                else: 
                                    if is_curr_stat:
                                        sub_gap_dur = (split_time - curr_gap_start).total_seconds() / 60
                                        if sub_gap_dur >= 0: timeline_events.append({'type': 'gap', 'start': curr_gap_start.strftime('%I:%M %p'), 'end': split_time.strftime('%I:%M %p'), 'duration': int(sub_gap_dur), 'activity': get_gap_label(sub_gap_dur, curr_loc, visited_places_df, curr_gap_start, split_time), 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                                        curr_gap_start, curr_move, transit_modes = split_time, new_move, [new_move]
                                    else:
                                        if new_move not in transit_modes: transit_modes.append(new_move)
                                        curr_move = new_move

                            final_dur = (gap_end_dt - curr_gap_start).total_seconds() / 60
                            if final_dur > 0:
                                act_label = f"On the way ({' + '.join(transit_modes)})" if transit_modes else get_gap_label(final_dur, curr_loc, visited_places_df, curr_gap_start, gap_end_dt) if curr_move.upper() == "- STATIONARY -" else f"On the way"
                                timeline_events.append({'type': 'gap', 'start': curr_gap_start.strftime('%I:%M %p'), 'end': gap_end_dt.strftime('%I:%M %p'), 'duration': int(final_dur), 'activity': act_label, 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
            
            current_loc, current_move = "", ""
            if not day_locs.empty:
                past_locs = day_locs[day_locs['Loc_DT'] <= current_start]
                current_loc, current_move = (past_locs.iloc[-1]['Place'], past_locs.iloc[-1]['Move']) if not past_locs.empty else (day_locs.iloc[0]['Place'], day_locs.iloc[0]['Move'])

            if row['Activity'] != 'CURRENT_TIME_MARKER':
                dur_mins = (current_end - current_start).total_seconds() / 60
                sub_str, chk_str = str(row['Sub_Activities']).strip().title(), str(row['check_list']).strip()
                display_sub = f"☑️ {chk_str}" if chk_str and not sub_str else (f"{sub_str} | ☑️ {chk_str}" if chk_str and sub_str else sub_str)

                timeline_events.append({'type': 'task', 'start': current_start.strftime('%I:%M %p'), 'end': current_end.strftime('%I:%M %p'), 'duration': int(dur_mins), 'activity': str(row['Activity']).upper(), 'sub': display_sub, 'notes': str(row['Notes']), 'place': str(current_loc).strip(), 'move': str(current_move).strip()})
            
            if last_end_time is None or current_end > last_end_time: last_end_time = current_end
        
        for event in timeline_events:
            eh, em = divmod(event['duration'], 60)
            dur_display = f"{eh}h {em}m" if eh > 0 and em > 0 else (f"{eh}h" if eh > 0 else (f"{em}m" if em > 0 else "<1m"))

            if event['type'] == 'transition':
                st.markdown(f"<div style='background-color: #fff3e0; border: 1px solid #ffb74d; padding: 8px; border-radius: 6px; margin-bottom: 10px; text-align: center; color: #e65100; font-size: 14px;'><b>{event['start']} - {event['end']}</b> | ⏳ Transition Time: {dur_display}</div>", unsafe_allow_html=True)
            elif event['type'] == 'gap':
                if event['activity'].startswith('On the way'):
                    st.markdown(f"<div style='background-color: #e0f7fa; border-left: 6px solid #00838f; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 10px 15px; border-radius: 4px; margin-bottom: 10px;'><div style='color: #888; font-size: 14px;'>{event['start']} - {event['end']} ({dur_display})</div><div style='color: #00838f; font-weight: bold; font-size: 16px;'>🛣️ {event['activity']}</div></div>", unsafe_allow_html=True)
                elif event['duration'] < 5:
                    place_str = str(event.get('place', '')).strip()
                    loc_html_gap = f"<div style='color: #0097a7; font-size: 14px; font-weight: 500; margin-top: 4px;'>📍 {place_str}</div>" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else ""
                    st.markdown(f"<div style='background-color: #e0f2f1; border-left: 6px solid #00acc1; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 10px 15px; border-radius: 4px; margin-bottom: 10px;'><div style='color: #888; font-size: 14px;'>{event['start']} - {event['end']} ({dur_display})</div><div style='color: #00acc1; font-weight: bold; font-size: 16px;'>{event['activity']}</div>{loc_html_gap}</div>", unsafe_allow_html=True)
                else:
                    place_str = str(event.get('place', '')).strip()
                    loc_html_gap = f"<br><span style='color: #d32f2f; font-size: 13px; font-weight: 500;'>📍 {place_str}</span>" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else ""
                    st.markdown(f"<div style='background-color: #fafafa; border: 2px dashed #cccccc; padding: 10px; border-radius: 8px; margin-bottom: 10px; text-align: center; color: #888;'><b>{event['start']} - {event['end']}</b> (Gap: {dur_display})<br><span style='color: #00acc1; font-weight: bold; font-size: 16px;'>{event['activity']}</span>{loc_html_gap}</div>", unsafe_allow_html=True)
            else:
                cat = event['activity']
                border_color = "#ff4b4b" if cat in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY", "PEOPLE"] else ("#0068c9" if cat in ["WORK", "REPORT", "TASK"] else ("#2e7b32" if cat == "HEALTH" else ("#ff9f36" if cat in ["SLEEP", "PRE", "TEA", "OUT"] else ("#29b6f6" if cat == "FREE TIME" else "#555555"))))
                sub_text = f"<br><b>{event['sub']}</b>" if event['sub'] else ""
                note_val = str(event.get('notes', '')).strip()
                note_text = f"<br><span style='font-size: 13px; color: #666;'>{note_val}</span>" if note_val and note_val not in ["Checked off", "Auto-logged via Timer"] else ""
                
                place_str, move_str = str(event.get('place', '')).strip(), str(event.get('move', '')).strip()
                loc_text = (f"🛣️ On the way ({move_str}) near {place_str}" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else f"🛣️ On the way ({move_str})") if move_str and move_str.upper() != "- STATIONARY -" else (f"📍 {place_str}" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else "")
                loc_html = f"<div style='color: #d32f2f; font-size: 13px; font-weight: 500; margin-top: 4px;'>{loc_text}</div>" if loc_text else ""
                
                st.markdown(f"<div style='background-color: white; border-left: 6px solid {border_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 10px 15px; border-radius: 4px; margin-bottom: 10px;'><div style='color: #888; font-size: 14px;'>{event['start']} - {event['end']} ({dur_display})</div><div style='color: {border_color}; font-weight: bold; font-size: 16px;'>{event['activity']}</div><div style='color: #333;'>{sub_text}{note_text}</div>{loc_html}</div>", unsafe_allow_html=True)
                
        st.markdown("---")
        st.markdown("<h4 style='text-align: center; color: #555;'>📊 Daily Summary</h4>", unsafe_allow_html=True)
        total_tracked = sum(e['duration'] for e in timeline_events if e['type'] == 'task')
        total_gap = sum(e['duration'] for e in timeline_events if e['type'] == 'gap' and e['activity'] == 'Unlogged Time / Break')
        total_transit = sum(e['duration'] for e in timeline_events if e['type'] == 'gap' and e['activity'] != 'Unlogged Time / Break')
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1: st.metric(label="Total Tracked Time", value=f"{int(total_tracked // 60)}h {int(total_tracked % 60)}m")
        with col_s2: st.metric(label="Total Unlogged Time", value=f"{int(total_gap // 60)}h {int(total_gap % 60)}m")
        with col_s3: st.metric(label="Total Transit & Stops", value=f"{int(total_transit // 60)}h {int(total_transit % 60)}m")
            
        category_totals = {}
        for e in timeline_events:
            if e['type'] == 'task':
                category_totals[e['activity']] = category_totals.get(e['activity'], 0) + e['duration']
                
        if total_transit > 0: category_totals['TRANSIT & STOPS'] = total_transit
            
        if category_totals:
            cat_df = pd.DataFrame(list(category_totals.items()), columns=['Category', 'Minutes']).sort_values(by='Minutes', ascending=False)
            cat_cols = st.columns(min(len(cat_df), 4))
            for idx, row in cat_df.iterrows():
                with cat_cols[idx % 4 if len(cat_df) >= 4 else idx]: st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:8px; text-align:center; margin-bottom:10px;'><b style='color:#333;'>{row['Category']}</b><br><span style='color:#0068c9;'>{int(row['Minutes'] // 60)}h {int(row['Minutes'] % 60)}m</span></div>", unsafe_allow_html=True)

    # ==========================================
    # TAB 2: HYDRATION
    # ==========================================
    with tab2:
        st.markdown("<h3 style='text-align: center; color: #0288d1;'>💧 Hydration Tracker</h3>", unsafe_allow_html=True)
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            if st.button("🥃 + 250 ml", use_container_width=True):
                smart_append_row(get_main_spreadsheet().worksheet("water_log"), [today_str, now.strftime('%H:%M'), 250])
                get_water_log.clear() 
                st.rerun()
        with col_w2:
            if st.button("🚰 + 500 ml", use_container_width=True):
                smart_append_row(get_main_spreadsheet().worksheet("water_log"), [today_str, now.strftime('%H:%M'), 500])
                get_water_log.clear() 
                st.rerun()
        with col_w3:
            if st.button("🥛 + 1000 ml", use_container_width=True):
                smart_append_row(get_main_spreadsheet().worksheet("water_log"), [today_str, now.strftime('%H:%M'), 1000])
                get_water_log.clear() 
                st.rerun()

        water_df['Date_dt'] = pd.to_datetime(water_df['Date'], errors='coerce')
        t_day, t_week, t_month = st.tabs(["Today", "Past 7 Days", "This Month"])
        with t_day:
            today_sum = water_df[water_df['Date'] == today_str]['Amount_ml'].sum()
            st.markdown(f"<h2 style='text-align: center; color: #0288d1;'>{int(today_sum)} ml logged today</h2>", unsafe_allow_html=True)
            st.progress(min(today_sum / 3500.0, 1.0))
            if not water_df[water_df['Date'] == today_str].empty: st.dataframe(water_df[water_df['Date'] == today_str][['Time', 'Amount_ml']].sort_values('Time', ascending=False), use_container_width=True, hide_index=True)
        with t_week:
            last_7 = water_df[water_df['Date_dt'] >= (pd.to_datetime(today_str) - timedelta(days=6))].copy()
            if not last_7.empty: st.bar_chart(last_7.groupby(last_7['Date_dt'].dt.strftime('%a, %b %d'))['Amount_ml'].sum(), color="#29b6f6")
        with t_month:
            this_month = water_df[water_df['Date_dt'].dt.month == pd.to_datetime(today_str).month].copy()
            if not this_month.empty: st.line_chart(this_month.groupby(this_month['Date_dt'].dt.day)['Amount_ml'].sum(), color="#0288d1")

    # ==========================================
    # TAB 3: PLACES DATABASE
    # ==========================================
    with tab3:
        st.markdown("<h3 style='text-align: center; color: #555;'>📍 Visited Places Database</h3>", unsafe_allow_html=True)
        if st.button("🔄 Generate & Sync to Google Sheets", type="primary", use_container_width=True):
            with st.spinner("Analyzing location history and syncing..."):
                raw_loc = get_location_data()
                valid_visits = []
                for _, row in raw_loc.iterrows():
                    m_raw, p_raw, d_raw, t_raw = str(row.get('Move', '')).strip(), str(row.get('Place', '')).strip(), str(row.get('Date', '')).strip(), str(row.get('Time', '')).strip()
                    if any(k in m_raw.upper() for k in ['BIKE', 'WALK', 'TOTO', 'AUTO', 'BUS', 'CAR', 'TRAIN', 'CYCLE', 'SCOOTER', 'VAN']): continue
                    a_place = p_raw if p_raw and p_raw.upper() not in ["I", "NAN", "NONE"] else m_raw
                    if not a_place or a_place.upper() in ["I", "NAN", "NONE", "- STATIONARY -"]: continue
                    purpose = get_short_stop_label(a_place)
                    rm_raw = str(row.get('Remark', '')).strip()
                    if rm_raw and rm_raw.upper() not in ["I", "NAN", "NONE", "LOGGED ARRIVAL", "QUICK HOME LOG", "UPDATE DETAILS LATER"]: purpose = rm_raw
                    valid_visits.append({"Place": a_place, "Purpose": purpose, "Visit_DateTime": f"{d_raw.split(' ')[0] if ' ' in d_raw else d_raw} {t_raw}"})
                    
                if valid_visits:
                    v_df = pd.DataFrame(valid_visits)
                    grouped = v_df.groupby(['Place', 'Purpose'])['Visit_DateTime'].apply(lambda x: '\n'.join(list(dict.fromkeys(x)))).reset_index()
                    try:
                        client = init_connection()
                        ss = client.open("sk_money_location")
                        try: ws = ss.worksheet("VISITED_PLACES")
                        except gspread.exceptions.WorksheetNotFound: ws = ss.add_worksheet(title="VISITED_PLACES", rows="1000", cols="3")
                            
                        upload_data = [["Place", "Purpose", "Visit Dates & Times"]] + grouped.values.tolist()
                        ws.clear()
                        ws.update(values=upload_data, range_name="A1")
                        
                        st.success("✅ 'VISITED_PLACES' tab successfully created/updated in your Google Sheet!")
                        st.dataframe(grouped, use_container_width=True, hide_index=True)
                    except Exception as e:
                        st.error(f"Failed to write to Google Sheets: {e}")
                else:
                    st.info("No stationary places found to log.")

except Exception as e: st.error(f"System Error: {e}")
