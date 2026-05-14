import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
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
    footer {visibility: hidden;}
    .block-container {padding-top: 4rem; padding-bottom: 2rem;}
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

def get_short_stop_label(place):
    p = str(place).upper()
    if "HOME" in p: return "🏠 Home Base"
    if "KARIM" in p: return "🔑 Key Drop / Pickup"
    if any(k in p for k in ["FRUIT", "SHOP", "STORE", "MARKET", "MALL"]): return "🛒 Quick Errand"
    if any(k in p for k in ["BUS", "STAND", "STATION", "STOP"]): return "🚏 Transit Wait"
    if any(k in p for k in ["SCHOOL", "MADRASA"]): return "🏫 School / Education"
    return "📍 General Visit"

def parse_duration_to_minutes(dur_str):
    try:
        h, m = map(int, str(dur_str).strip().split(':'))
        return (h * 60) + m
    except: return 0

# ==========================================
# Main App UI
# ==========================================
try:
    log_df = get_activity_log() 
    loc_df = get_location_data() 
    visited_places_df = get_visited_places()
    
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    today_str = now.strftime('%Y-%m-%d')

    st.markdown("<h2 style='text-align: center; color: #555; margin-top: 0px;'>📊 Daily Data & Audit Hub</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["⏳ Timeline Audit", "📋 Daily Summary", "📅 Weekly Matrix", "📍 Places"])

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
                
        selected_timeline_date = st.date_input("Select Date to Review Timeline", value=now.date(), key="timeline_date_sel")
        selected_date_str = selected_timeline_date.strftime('%Y-%m-%d')
        formatted_target_date = selected_timeline_date.strftime('%d.%m.%y') 
        prev_date_str = (selected_timeline_date - timedelta(days=1)).strftime('%Y-%m-%d')
        
        def get_gap_label(dur, loc, visited_df, start_dt, end_dt, is_long_gap=False):
            if "HOME" in str(loc).upper(): return get_short_stop_label(loc) if not is_long_gap and dur <= 10 else "Unlogged / Free Time"
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
            return get_short_stop_label(loc) if not is_long_gap and dur <= 10 else "Unlogged / Free Time"
        
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
        day_locs = loc_df_safe[loc_df_safe['Parsed_Date'].isin([selected_timeline_date, selected_timeline_date - timedelta(days=1)])].copy()
        
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
        today_locs = day_locs[day_locs['Parsed_Date'] == selected_timeline_date] if not day_locs.empty else pd.DataFrame()
        if not today_locs.empty and today_locs['Loc_DT'].min() < start_time_limit: 
            start_time_limit = today_locs['Loc_DT'].min()
            
        if not day_logs.empty and day_logs.iloc[0]['Display_Start'] < start_time_limit and day_logs.iloc[0]['Activity'] != 'CURRENT_TIME_MARKER': 
            start_time_limit = day_logs.iloc[0]['Display_Start']
            
        if start_time_limit < day_start_dt:
            start_time_limit = day_start_dt

        last_end_time = start_time_limit
        timeline_events = []
        
        for _, row in day_logs.iterrows():
            current_start, current_end = row['Display_Start'], row['Display_End']
            
            if last_end_time and current_start > last_end_time:
                gap_duration = (current_start - last_end_time).total_seconds() / 60
                if gap_duration > 0:
                    if gap_duration <= 10: 
                        timeline_events.append({'type': 'transition', 'start': last_end_time.strftime('%I:%M %p'), 'end': current_start.strftime('%I:%M %p'), 'duration': int(gap_duration), 'activity': 'Bio Break / Preparation', 'sub': '', 'notes': '', 'place': '', 'move': ''})
                    else: 
                        # --- NEW LOGIC: FIRST 10 MIN BIO BREAK ---
                        prep_start_dt = last_end_time
                        prep_end_dt = last_end_time + timedelta(minutes=10)
                        
                        timeline_events.append({
                            'type': 'transition', 
                            'start': prep_start_dt.strftime('%I:%M %p'), 
                            'end': prep_end_dt.strftime('%I:%M %p'), 
                            'duration': 10, 
                            'activity': 'Bio Break / Preparation', 
                            'sub': '', 'notes': '', 'place': '', 'move': ''
                        })
                        
                        # The remaining gap starts after the 10 min prep
                        gap_start_dt = prep_end_dt
                        gap_end_dt = current_start
                        
                        locs_in_gap = day_locs[(day_locs['Loc_DT'] > gap_start_dt) & (day_locs['Loc_DT'] < gap_end_dt)] if not day_locs.empty else pd.DataFrame()
                            
                        def get_loc_state_at_time(t):
                            if day_locs.empty: return "", "- Stationary -"
                            past = day_locs[day_locs['Loc_DT'] <= t]
                            return (past.iloc[-1]['Place'], past.iloc[-1]['Move']) if not past.empty else (day_locs.iloc[0]['Place'], day_locs.iloc[0]['Move'])
                            
                        curr_gap_start = gap_start_dt
                        curr_loc, curr_move = get_loc_state_at_time(curr_gap_start)
                        transit_modes = [curr_move] if curr_move.upper() != "- STATIONARY -" else []
                        
                        if locs_in_gap.empty:
                            dur_left = (gap_end_dt - gap_start_dt).total_seconds() / 60
                            act_label = f"On the way ({' + '.join(transit_modes)})" if transit_modes else get_gap_label(dur_left, curr_loc, visited_places_df, gap_start_dt, gap_end_dt, is_long_gap=True)
                            timeline_events.append({'type': 'gap', 'start': gap_start_dt.strftime('%I:%M %p'), 'end': gap_end_dt.strftime('%I:%M %p'), 'duration': int(dur_left), 'activity': act_label, 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                        else:
                            for _, l_row in locs_in_gap.iterrows():
                                split_time, new_move, new_loc = l_row['Loc_DT'], str(l_row['Move']).strip(), str(l_row['Place']).strip()
                                is_new_stat, is_curr_stat = new_move.upper() == "- STATIONARY -", curr_move.upper() == "- STATIONARY -"
                                
                                if is_new_stat:
                                    if not is_curr_stat:
                                        sub_gap_dur = (split_time - curr_gap_start).total_seconds() / 60
                                        if sub_gap_dur > 0: timeline_events.append({'type': 'gap', 'start': curr_gap_start.strftime('%I:%M %p'), 'end': split_time.strftime('%I:%M %p'), 'duration': int(sub_gap_dur), 'activity': f"On the way ({' + '.join(transit_modes)})" if transit_modes else "On the way", 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                                        curr_gap_start, curr_loc, curr_move, transit_modes = split_time, new_loc, new_move, []
                                    elif new_loc.upper() != curr_loc.upper() and curr_loc != "":
                                        sub_gap_dur = (split_time - curr_gap_start).total_seconds() / 60
                                        if sub_gap_dur > 0: timeline_events.append({'type': 'gap', 'start': curr_gap_start.strftime('%I:%M %p'), 'end': split_time.strftime('%I:%M %p'), 'duration': int(sub_gap_dur), 'activity': get_gap_label(sub_gap_dur, curr_loc, visited_places_df, curr_gap_start, split_time, is_long_gap=True), 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                                        curr_gap_start, curr_loc, curr_move = split_time, new_loc, new_move
                                else: 
                                    if is_curr_stat:
                                        sub_gap_dur = (split_time - curr_gap_start).total_seconds() / 60
                                        if sub_gap_dur > 0: timeline_events.append({'type': 'gap', 'start': curr_gap_start.strftime('%I:%M %p'), 'end': split_time.strftime('%I:%M %p'), 'duration': int(sub_gap_dur), 'activity': get_gap_label(sub_gap_dur, curr_loc, visited_places_df, curr_gap_start, split_time, is_long_gap=True), 'sub': '', 'notes': '', 'place': str(curr_loc).strip(), 'move': ""})
                                        curr_gap_start, curr_move, transit_modes = split_time, new_move, [new_move]
                                    else:
                                        if new_move not in transit_modes: transit_modes.append(new_move)
                                        curr_move = new_move

                            final_dur = (gap_end_dt - curr_gap_start).total_seconds() / 60
                            if final_dur > 0:
                                act_label = f"On the way ({' + '.join(transit_modes)})" if transit_modes else get_gap_label(final_dur, curr_loc, visited_places_df, curr_gap_start, gap_end_dt, is_long_gap=True) if curr_move.upper() == "- STATIONARY -" else f"On the way"
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
                html = (
                    f"<div style='display: flex; justify-content: center; align-items: center; background-color: #fff3e0; border: 1px solid #ffb74d; padding: 6px 12px; border-radius: 20px; margin-bottom: 10px; margin-left: 10%; margin-right: 10%;'>"
                    f"<span style='color: #e65100; font-size: 13px; font-weight: 500;'>⏳ Bio Break / Preparation: {event['start']} - {event['end']} ({dur_display})</span>"
                    f"</div>"
                )
                st.markdown(html, unsafe_allow_html=True)
            elif event['type'] == 'gap':
                if event['activity'] == 'Unlogged / Free Time':
                    place_str = str(event.get('place', '')).strip()
                    loc_html_gap = f"<div style='font-size: 12px; color: #d32f2f; font-weight: 500; margin-top: 4px;'>📍 {place_str}</div>" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else ""
                    html = (
                        f"<div style='display: flex; justify-content: space-between; align-items: center; background-color: #fafafa; border: 2px dashed #ccc; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px;'>"
                        f"<div style='flex: 1;'>"
                        f"<div style='font-size: 15px; font-weight: bold; color: #888;'>{event['activity']}</div>"
                        f"{loc_html_gap}"
                        f"</div>"
                        f"<div style='text-align: right; min-width: 110px;'>"
                        f"<div style='font-size: 13px; font-weight: 600; color: #666;'>{event['start']} - {event['end']}</div>"
                        f"<div style='font-size: 12px; color: #888; background: #eee; display: inline-block; padding: 2px 8px; border-radius: 12px; margin-top: 4px;'>⏱️ {dur_display}</div>"
                        f"</div>"
                        f"</div>"
                    )
                elif event['activity'].startswith('On the way'):
                    html = (
                        f"<div style='display: flex; justify-content: space-between; align-items: center; background-color: #e0f7fa; border-left: 5px solid #00838f; padding: 12px 16px; border-radius: 6px; margin-bottom: 10px;'>"
                        f"<div style='flex: 1; font-size: 15px; font-weight: bold; color: #00838f;'>🛣️ {event['activity']}</div>"
                        f"<div style='text-align: right; min-width: 110px;'>"
                        f"<div style='font-size: 13px; font-weight: 600; color: #006064;'>{event['start']} - {event['end']}</div>"
                        f"<div style='font-size: 12px; color: #00838f; background: #b2ebf2; display: inline-block; padding: 2px 8px; border-radius: 12px; margin-top: 4px;'>⏱️ {dur_display}</div>"
                        f"</div>"
                        f"</div>"
                    )
                else:
                    place_str = str(event.get('place', '')).strip()
                    loc_html_gap = f"<div style='font-size: 12px; color: #0097a7; font-weight: 500; margin-top: 4px;'>📍 {place_str}</div>" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else ""
                    html = (
                        f"<div style='display: flex; justify-content: space-between; align-items: center; background-color: #e0f2f1; border-left: 5px solid #00acc1; padding: 12px 16px; border-radius: 6px; margin-bottom: 10px;'>"
                        f"<div style='flex: 1;'>"
                        f"<div style='font-size: 15px; font-weight: bold; color: #00acc1;'>{event['activity']}</div>"
                        f"{loc_html_gap}"
                        f"</div>"
                        f"<div style='text-align: right; min-width: 110px;'>"
                        f"<div style='font-size: 13px; font-weight: 600; color: #00695c;'>{event['start']} - {event['end']}</div>"
                        f"<div style='font-size: 12px; color: #00acc1; background: #b2dfdb; display: inline-block; padding: 2px 8px; border-radius: 12px; margin-top: 4px;'>⏱️ {dur_display}</div>"
                        f"</div>"
                        f"</div>"
                    )
                st.markdown(html, unsafe_allow_html=True)
            else:
                cat = event['activity']
                border_color = "#ff4b4b" if cat in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY", "PEOPLE"] else ("#0068c9" if cat in ["WORK", "REPORT", "TASK"] else ("#2e7b32" if cat == "HEALTH" else ("#ff9f36" if cat in ["SLEEP", "PRE", "TEA", "OUT"] else ("#29b6f6" if cat == "FREE TIME" else "#555555"))))
                
                sub_text = f"<span style='color: #555; font-size: 14px; font-weight: 500;'>{event['sub']}</span>" if event['sub'] else ""
                note_val = str(event.get('notes', '')).strip()
                note_text = f"<div style='font-size: 12px; color: #888; margin-top: 4px;'>📝 {note_val}</div>" if note_val and note_val not in ["Checked off", "Auto-logged via Timer"] else ""
                
                place_str, move_str = str(event.get('place', '')).strip(), str(event.get('move', '')).strip()
                loc_text = (f"🛣️ On the way ({move_str}) near {place_str}" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else f"🛣️ On the way ({move_str})") if move_str and move_str.upper() != "- STATIONARY -" else (f"📍 {place_str}" if place_str and place_str.upper() not in ["I", "NAN", "NONE"] else "")
                loc_html = f"<div style='font-size: 12px; color: #0288d1; margin-top: 4px; font-weight: 500;'>{loc_text}</div>" if loc_text else ""
                
                html = (
                    f"<div style='display: flex; justify-content: space-between; align-items: center; background-color: white; border-left: 5px solid {border_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 12px 16px; border-radius: 6px; margin-bottom: 10px;'>"
                    f"<div style='flex: 1; padding-right: 15px;'>"
                    f"<div style='display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;'>"
                    f"<span style='font-size: 16px; font-weight: 700; color: {border_color};'>{event['activity']}</span>"
                    f"{sub_text}"
                    f"</div>"
                    f"{note_text}"
                    f"{loc_html}"
                    f"</div>"
                    f"<div style='text-align: right; min-width: 110px;'>"
                    f"<div style='font-size: 13px; font-weight: 600; color: #333;'>{event['start']} - {event['end']}</div>"
                    f"<div style='font-size: 12px; color: #666; background: #f0f2f6; display: inline-block; padding: 2px 8px; border-radius: 12px; margin-top: 4px;'>⏱️ {dur_display}</div>"
                    f"</div>"
                    f"</div>"
                )
                st.markdown(html, unsafe_allow_html=True)
                
        # --- 1. DAILY SUMMARY (TIMELINE OVERVIEW) ---
        st.markdown("---")
        st.markdown("<h4 style='text-align: center; color: #555;'>📊 Daily Summary (24 Hours)</h4>", unsafe_allow_html=True)
        total_tracked = sum(e['duration'] for e in timeline_events if e['type'] == 'task')
        total_transit = sum(e['duration'] for e in timeline_events if e['type'] == 'gap' and e['activity'] != 'Unlogged / Free Time')
        total_bio_break = sum(e['duration'] for e in timeline_events if e['type'] == 'transition')
        
        # Calculate exactly how much time is unaccounted for out of the 1440 minutes in a day
        unlogged_24h = max(0, 1440 - total_tracked - total_transit - total_bio_break)
        
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1: st.metric(label="Total Tracked", value=f"{int(total_tracked // 60)}h {int(total_tracked % 60)}m")
        with col_s2: st.metric(label="Transit & Stops", value=f"{int(total_transit // 60)}h {int(total_transit % 60)}m")
        with col_s3: st.metric(label="Bio Break / Prep", value=f"{int(total_bio_break // 60)}h {int(total_bio_break % 60)}m")
        with col_s4: st.metric(label="Unlogged / Free", value=f"{int(unlogged_24h // 60)}h {int(unlogged_24h % 60)}m")
            
        category_totals = {}
        for e in timeline_events:
            if e['type'] == 'task':
                category_totals[e['activity']] = category_totals.get(e['activity'], 0) + e['duration']
                
        if total_transit > 0: category_totals['TRANSIT & STOPS'] = total_transit
        if total_bio_break > 0: category_totals['BIO BREAK / PREP'] = total_bio_break
        if unlogged_24h > 0: category_totals['UNLOGGED TIME'] = unlogged_24h
            
        if category_totals:
            cat_df = pd.DataFrame(list(category_totals.items()), columns=['Category', 'Minutes']).sort_values(by='Minutes', ascending=False)
            
            import plotly.graph_objects as go
            fig = go.Figure(data=[go.Pie(
                labels=cat_df['Category'], 
                values=cat_df['Minutes'], 
                hole=0.4,
                textinfo='label+percent',
                hoverinfo='label+value+percent'
            )])
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350, showlegend=True)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # ==========================================
    # TAB 2: DAILY SUMMARY (COMPACT ACTIVITY CARDS)
    # ==========================================
    with tab2:
        col_t2, col_d2 = st.columns([7, 3])
        with col_t2: 
            st.markdown("<h3 style='color: #555; margin-top: 0px;'>📋 Daily Overview</h3>", unsafe_allow_html=True)
        with col_d2:
            summary_date = st.date_input("Select Date for Overview", value=now.date(), key="summary_date")
            
        summary_date_str = summary_date.strftime('%Y-%m-%d')
        
        day_logs = log_df[(log_df['Date'] == summary_date_str) & (log_df['End_Time'] != 'RUNNING')].copy()
        
        if not day_logs.empty:
            day_logs['Total_Minutes'] = day_logs['Duration'].apply(parse_duration_to_minutes)
            total_tracked_day = day_logs['Total_Minutes'].sum()
            unlogged_day = max(0, 1440 - total_tracked_day)
            
            grouped = day_logs.groupby('Activity')
            summary_data = []
            
            for act_name, group in grouped:
                total_mins = group['Total_Minutes'].sum()
                summary_data.append({
                    'Activity': act_name,
                    'Total_Minutes': total_mins,
                    'Count': len(group),
                    'Group': group.sort_values('Start_Time')
                })
                
            summary_data.sort(key=lambda x: x['Total_Minutes'], reverse=True)
            
            col_left, col_right = st.columns(2)
            for idx, item in enumerate(summary_data):
                target_col = col_left if idx % 2 == 0 else col_right
                with target_col:
                    h, m = divmod(item['Total_Minutes'], 60)
                    act_name = item['Activity']
                    count = item['Count']
                    
                    cat = act_name.upper()
                    if cat in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY", "PEOPLE"]: icon = "❤️"
                    elif cat in ["WORK", "REPORT", "TASK"]: icon = "💼"
                    elif cat == "HEALTH": icon = "🏃"
                    elif cat in ["SLEEP", "PRE", "TEA", "OUT"]: icon = "☕"
                    else: icon = "📌"
                    
                    exp_title = f"{icon} {act_name} | {int(h)}h {int(m):02d}m | {count} items"
                    with st.expander(exp_title):
                        for _, row in item['Group'].iterrows():
                            sub = str(row['Sub_Activities']).strip()
                            if not sub: sub = "General Task"
                            chk = str(row['check_list']).strip()
                            if chk: sub += f" <span style='color: #0068c9;'>(☑️ {chk})</span>"
                            
                            html = (
                                f"<div style='display: flex; justify-content: space-between; align-items: center; background-color: #f8f9fa; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #ccc; margin-bottom: 6px;'>"
                                f"<div style='font-size: 14px; font-weight: 500; color: #333;'>{sub}</div>"
                                f"<div style='font-size: 12px; color: #666; font-weight: bold; background: #e2e8f0; padding: 2px 6px; border-radius: 4px; white-space: nowrap;'>{row['Start_Time']} - {row['End_Time']} &nbsp;|&nbsp; <span style='color:#0068c9;'>{row['Duration']}</span></div>"
                                f"</div>"
                            )
                            st.markdown(html, unsafe_allow_html=True)
                            
            st.markdown("<br>", unsafe_allow_html=True)
            h_un, m_un = divmod(unlogged_day, 60)
            with st.expander(f"🕳️ UNLOGGED TIME | {int(h_un)}h {int(m_un):02d}m"):
                st.markdown("<div style='text-align: center; padding: 15px; color: #888;'><i>This time includes your transit, breaks, and untracked gaps.</i></div>", unsafe_allow_html=True)

        else:
            st.info(f"No completed activities found for {summary_date.strftime('%d %b %Y')}.")

    # ==========================================
    # TAB 3: WEEKLY SUMMARY (MATRIX)
    # ==========================================
    with tab3:
        st.markdown("<h3 style='text-align: center; color: #555; margin-top: 0px;'>📅 Weekly Activity Matrix</h3>", unsafe_allow_html=True)
        
        last_7_dates = sorted([(now.date() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)])
        weekly_logs = log_df[(log_df['Date'].isin(last_7_dates)) & (log_df['End_Time'] != 'RUNNING')].copy()
        
        if not weekly_logs.empty:
            weekly_logs['Hours'] = weekly_logs['Duration'].apply(lambda x: parse_duration_to_minutes(x) / 60.0)
            pivot = weekly_logs.pivot_table(index="Activity", columns="Date", values="Hours", aggfunc="sum").fillna(0)
            
            for d in last_7_dates:
                if d not in pivot.columns:
                    pivot[d] = 0.0
            
            pivot = pivot[last_7_dates]
            unlogged_row = {}
            for d in last_7_dates:
                tracked_that_day = pivot[d].sum()
                unlogged_row[d] = max(0.0, 24.0 - tracked_that_day)
                
            pivot.loc["🕳️ UNLOGGED TIME"] = unlogged_row
            
            def format_matrix_hours(h):
                if h <= 0.01: return "-"
                ih = int(h)
                im = int(round((h - ih) * 60))
                if im == 60:
                    ih += 1
                    im = 0
                if ih > 0 and im > 0: return f"{ih}h {im}m"
                elif ih > 0: return f"{ih}h"
                else: return f"{im}m"
                
            formatted_pivot = pivot.map(format_matrix_hours)
            st.dataframe(formatted_pivot, use_container_width=True, height=550)
        else:
            st.info("No completed activities found for the last 7 days.")

    # ==========================================
    # TAB 4: PLACES DATABASE
    # ==========================================
    with tab4:
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
                    grouped = v_df.groupby(['Place', 'Purpose'])['Visit_DateTime'].apply(lambda x: '\\n'.join(list(dict.fromkeys(x)))).reset_index()
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
