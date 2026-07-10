import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="SK Location Tracker", page_icon="📍", layout="centered")

# --- MOBILE KEYBOARD FIX ---
st.markdown("""
    <style>
    div[data-baseweb="select"] input {
        pointer-events: none !important;
    }
    </style>
""", unsafe_allow_html=True)

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

# Initialize Session States
if 'route_active' not in st.session_state: st.session_state.route_active = False
if 'route_type' not in st.session_state: st.session_state.route_type = None 
if 'active_route' not in st.session_state: st.session_state.active_route = ""
if 'current_people' not in st.session_state: st.session_state.current_people = "I"
if 'current_move' not in st.session_state: st.session_state.current_move = "BIKE"
if 'retro_time' not in st.session_state: st.session_state.retro_time = get_ist_now().time()
if 'locked_date' not in st.session_state: st.session_state.locked_date = get_ist_now().date()
if 'locked_time' not in st.session_state: st.session_state.locked_time = get_ist_now().time()
if 'last_used_route' not in st.session_state: st.session_state.last_used_route = None
if 'target_destination' not in st.session_state: st.session_state.target_destination = ""
if 'stop_active' not in st.session_state: st.session_state.stop_active = False
if 'stop_start_time' not in st.session_state: st.session_state.stop_start_time = None

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("sk_money_location"), client.open("PEOPLE")

try:
    sh, sh_people = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    st.stop()

# --- CACHING ENGINE (Only Location Needed) ---
@st.cache_data(ttl=600)
def load_config():
    try: return pd.DataFrame(sh.worksheet("CONFIG").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_location_data():
    try: return pd.DataFrame(sh.worksheet("LOCATION_DATA").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_money_data(): # Kept only to clear cache when paying fare
    try: return pd.DataFrame(sh.worksheet("MONEY_DATA").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_working_hours():
    try: return pd.DataFrame(sh.worksheet("WORKING_HOURS").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_people_names():
    try: return pd.DataFrame(sh_people.worksheet("People").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_interactions():
    try: return pd.DataFrame(sh_people.worksheet("People Interaction").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

ACCOUNT_HEADERS = ["A. Cash:", "B. Bank Accounts:", "C. Credit Cards:", "D. Digital Wallet:", "E. Loan:", "F. Members:"]

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

def get_clean_accounts():
    raw = get_list("Accounts")
    return [a for a in raw if a not in ACCOUNT_HEADERS]

def get_location_logic():
    logic = {}
    if 'Area' in config_df.columns and 'Specific_Place' in config_df.columns:
        for index, row in config_df.iterrows():
            area = str(row['Area']).strip()
            place = str(row['Specific_Place']).strip()
            if area and place and area.lower() != 'nan' and place.lower() != 'nan':
                if area not in logic: logic[area] = []
                if place not in logic[area]: logic[area].append(place)
    return logic

def get_transit_rules():
    rules = {}
    if 'Area' in config_df.columns and 'Specific_Place' in config_df.columns and 'Def_Mode' in config_df.columns:
        has_fare = 'Def_Fare' in config_df.columns
        grouped = config_df.groupby('Area')
        for area, group in grouped:
            places = group['Specific_Place'].tolist()
            modes = group['Def_Mode'].tolist()
            fares = group['Def_Fare'].tolist() if has_fare else ["0"] * len(places)
            for i in range(len(places) - 1):
                p1, p2 = str(places[i]).strip(), str(places[i+1]).strip()
                mode, fare = str(modes[i]).strip().upper(), str(fares[i]).strip()
                if p1 and p2:
                    rule_mode = mode if mode and mode not in ['NAN', 'NONE'] else None
                    try: rule_fare = float(fare) if fare.lower() not in ['nan', '', 'none'] else 0.0
                    except: rule_fare = 0.0
                    if rule_mode or rule_fare > 0:
                        rules[frozenset([p1, p2])] = {'mode': rule_mode, 'fare': rule_fare}
    return rules

def get_current_location_details():
    df_loc = load_location_data()
    if not df_loc.empty:
        last_record = df_loc.iloc[-1].to_dict()
        move_val = str(last_record.get('Move', '')).strip()
        if move_val in ["", "- Stationary -", "nan"]:
            loc = str(last_record.get('Place', '')).strip()
            date_str, time_str = str(last_record.get('Date', '')), str(last_record.get('Time', ''))
            duration_str = ""
            try:
                loc_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%y %H:%M")
                diff = get_ist_now().replace(tzinfo=None) - loc_dt
                tot_sec = int(diff.total_seconds())
                if tot_sec >= 0:
                    days, rem = divmod(tot_sec, 86400)
                    hrs, rem = divmod(rem, 3600)
                    mins, _ = divmod(rem, 60)
                    duration_str = f"{days}d {hrs}h" if days > 0 else (f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m")
            except: pass
            return loc, duration_str
    return None, None

def get_home_occupants(arriving_people_str):
    if get_ist_now().hour >= 14: return "I Baso, Suborno, Mother"
    df_loc = load_location_data()
    safe_arr = arriving_people_str.replace('I Baso', 'I, Baso')
    arr_set = set([p.strip() for p in safe_arr.split(',') if p.strip()])
    order = ["I", "Baso", "Suborno", "Mother"]
    
    if df_loc.empty:
        now_h = arr_set.union({"Baso", "Suborno", "Mother"})
        return ", ".join([p for p in order if p in now_h] + [p for p in now_h if p not in order]).replace("I, Baso", "I Baso")

    last_h_idx = next((i for i in range(len(df_loc)-1, -1, -1) if str(df_loc.iloc[i].get('Place','')).strip() == 'HOME' and str(df_loc.iloc[i].get('Move','')).strip() == '- Stationary -'), -1)

    if last_h_idx != -1:
        past_h_set = set([p.strip() for p in str(df_loc.iloc[last_h_idx].get('People','')).replace('I Baso', 'I, Baso').split(',') if p.strip()])
        if last_h_idx < len(df_loc) - 1:
            dep_set = set([p.strip() for p in str(df_loc.iloc[last_h_idx + 1].get('People','')).replace('I Baso', 'I, Baso').split(',') if p.strip()])
            now_h = (past_h_set - dep_set).union(arr_set)
        else: now_h = past_h_set.union(arr_set)
    else: now_h = arr_set.union({"Baso", "Suborno", "Mother"})
        
    return ", ".join([p for p in order if p in now_h] + [p for p in now_h if p not in order]).replace("I, Baso", "I Baso")

def sync_journey_state():
    if 'state_synced' not in st.session_state:
        df_loc = load_location_data()
        if not df_loc.empty:
            st.session_state.current_move = next((str(df_loc.iloc[i].get('Move','')).strip() for i in range(len(df_loc)-1,-1,-1) if str(df_loc.iloc[i].get('Move','')).strip() not in ["","- Stationary -","nan"]), "BIKE")
            
            recent_route = None
            if 'Remark' in df_loc.columns:
                for rem in reversed(df_loc['Remark'].tolist()):
                    if "Started Route:" in str(rem):
                        recent_route = str(rem).split("Started Route:")[-1].split("towards")[0].strip()
                        break
            st.session_state.last_used_route = recent_route

            last_rec = df_loc.iloc[-1].to_dict()
            m_val, p_val = str(last_rec.get('Move','')).strip(), str(last_rec.get('Place','')).strip().upper()
            
            if m_val in ["", "- Stationary -", "nan"] and p_val == "HOME": st.session_state.current_people = "I"
            else: st.session_state.current_people = str(last_rec.get('People', 'I'))
            
            if m_val not in ["", "- Stationary -", "nan"]:
                st.session_state.route_active = True
                rem = str(last_rec.get('Remark',''))
                if "Started Route:" in rem:
                    st.session_state.active_route = rem.split("Started Route:")[-1].split("towards")[0].strip()
                    if "towards" in rem: st.session_state.target_destination = rem.split("towards")[-1].strip()
                    st.session_state.route_type = "Dynamic"
                else: st.session_state.route_type = "Express" 
            else:
                st.session_state.route_active = False
                st.session_state.route_type = None
        st.session_state.state_synced = True

sync_journey_state()

# ==========================================
# APP LAYOUT
# ==========================================
st.title("📍 SK Location Tracker")

tab_location, tab_config = st.tabs(["📍 Route & Stops", "⚙️ Data Config"])
current_loc, loc_duration = get_current_location_details()
all_places_list = get_list("Places")

with tab_location:
    if 'target_destination' not in st.session_state: st.session_state.target_destination = ""

    # ==========================================
    # DYNAMIC AREA ROUTE EXPANDER
    # ==========================================
    with st.expander("🗺️ Dynamic Area Route", expanded=False):
        location_logic = get_location_logic()
        route_opts = list(location_logic.keys())
        
        if not st.session_state.route_active:
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                default_idx = route_opts.index(st.session_state.get('last_used_route')) if st.session_state.get('last_used_route') in route_opts else 0
                selected_route = st.selectbox("Select Route (Area)", route_opts, index=default_idx, key="dyn_route")
                places_for_route = location_logic.get(selected_route, ["-- No places mapped --"])
                
                is_sequential = selected_route.strip().lower().endswith('route')
                if is_sequential:
                    dir_col1, dir_col2 = st.columns([1, 1])
                    with dir_col1: route_direction = st.radio("Direction", ["Forward", "Return"], horizontal=True, key="dyn_dir")
                    if current_loc in places_for_route:
                        c_idx = places_for_route.index(current_loc)
                        available_places = places_for_route[c_idx + 1:] if route_direction == "Forward" else places_for_route[:c_idx][::-1]
                        if not available_places: available_places = places_for_route 
                    else: available_places = places_for_route if route_direction == "Forward" else places_for_route[::-1]
                else: available_places = places_for_route

                out_of_route = st.checkbox("📍 Visit place outside this route")
                if out_of_route:
                    dyn_next_stop_sel = st.selectbox("Next Stop (Other Place)", all_places_list + ["-- Type New --"], key="dyn_other_place")
                    dyn_next_stop = st.text_input("Type New Place Name", key="dyn_new_place") if dyn_next_stop_sel == "-- Type New --" else dyn_next_stop_sel
                else: dyn_next_stop = st.selectbox("Next Stop", available_places, key="dyn_next_stop")
                
                # --- SMART WARNINGS ---
                if dyn_next_stop and dyn_next_stop != "-- No places mapped --":
                    df_loc_warn = load_location_data()
                    if not df_loc_warn.empty and 'Place' in df_loc_warn.columns and 'Remark' in df_loc_warn.columns:
                        closed_remarks = df_loc_warn[(df_loc_warn['Place'].astype(str).str.strip() == dyn_next_stop) & (df_loc_warn['Remark'].astype(str).str.contains("Closed:", na=False))]
                        if not closed_remarks.empty:
                            last_closed = closed_remarks.iloc[-1]['Remark'].split("Closed:")[-1].strip()
                            if get_ist_now().strftime('%A').lower() in last_closed.lower(): st.warning(f"⚠️ **Note:** {dyn_next_stop} is usually marked as CLOSED on {last_closed}s!")
                    
                    df_wh_warn = load_working_hours()
                    if not df_wh_warn.empty and 'Place' in df_wh_warn.columns:
                        wh_match = df_wh_warn[df_wh_warn['Place'].astype(str).str.strip() == dyn_next_stop]
                        if not wh_match.empty:
                            curr_day_name = get_ist_now().strftime('%A')
                            def is_day_match(d_str):
                                d = str(d_str).strip()
                                return True if d == "All Days" or (d == "Mon-Fri" and curr_day_name in ["Monday","Tuesday","Wednesday","Thursday","Friday"]) or (d == "Sat-Sun" and curr_day_name in ["Saturday","Sunday"]) or curr_day_name.lower() in d.lower() else False
                            day_matches = wh_match[wh_match['Day'].apply(is_day_match)] if 'Day' in wh_match.columns else pd.DataFrame()
                            last_wh = day_matches.iloc[-1] if not day_matches.empty else wh_match.iloc[-1]

                            try:
                                open_t, close_t, curr_t = datetime.strptime(str(last_wh.get('Open','00:00')),"%H:%M").time(), datetime.strptime(str(last_wh.get('Close','23:59')),"%H:%M").time(), get_ist_now().time()
                                on_break = False
                                b_start, b_end = str(last_wh.get('Break_Start','')), str(last_wh.get('Break_End',''))
                                if b_start and b_end and b_start != 'nan' and b_end != 'nan':
                                    b_o, b_c = datetime.strptime(b_start,"%H:%M").time(), datetime.strptime(b_end,"%H:%M").time()
                                    if b_o <= curr_t <= b_c:
                                        on_break = True
                                        st.warning(f"⚠️ **Note:** {dyn_next_stop} is currently on BREAK/LUNCH! ({b_start} - {b_end}).")
                                if not on_break and not (open_t <= curr_t <= close_t): st.warning(f"⚠️ **Note:** {dyn_next_stop} might be closed right now! Hours: {last_wh.get('Open')} - {last_wh.get('Close')}.")
                            except: pass

                transit_rules = get_transit_rules()
                current_pair = frozenset([str(current_loc).strip(), str(dyn_next_stop).strip()]) if current_loc else None
                pre_mode = st.session_state.get('current_move', 'BIKE')
                base_fare = 0.0
                
                if current_pair in transit_rules:
                    if transit_rules[current_pair]['mode'] and transit_rules[current_pair]['mode'] not in ['WALK', 'BIKE', 'BIKE + WALK', 'TRAIN']:
                        pre_mode = transit_rules[current_pair]['mode']
                    base_fare = transit_rules[current_pair]['fare']

                move_options = ["BIKE", "WALK", "BIKE + WALK", "TOTO", "AUTO", "BUS", "TRAIN", "-- Type New --"]
                if pre_mode and pre_mode not in move_options: move_options.insert(0, pre_mode)
                default_mode_idx = move_options.index(pre_mode) if pre_mode in move_options else 0
                
                dyn_move_sel = st.selectbox("Travel Mode", move_options, index=default_mode_idx, key="dyn_move")
                dyn_move = st.text_input("Type New Travel Mode", key="dyn_new_move") if dyn_move_sel == "-- Type New --" else dyn_move_sel
                if dyn_move in ["WALK", "BIKE", "BIKE + WALK"]: base_fare = 0.0
                
            with d_col2:
                people_opts = get_list("People")
                if not people_opts: people_opts = ["I"]
                if "I" not in people_opts: people_opts.insert(0, "I")
                
                default_people_idx = people_opts.index(st.session_state.current_people) if st.session_state.current_people in people_opts else 0
                dyn_people = st.selectbox("Companions", people_opts, index=default_people_idx, key="dyn_people")
                
                total_people = len([p for p in dyn_people.replace('I Baso', 'I, Baso').split(',') if p.strip()]) if dyn_people != "I" else 1
                child_tix = st.number_input("Child/Half Fares (Included in Companions)", min_value=0, max_value=total_people, value=0, step=1, key="dyn_child")
                
                actual_adults = total_people - child_tix
                calc_fare = (actual_adults * base_fare) + (child_tix * (base_fare / 2))
                
                if base_fare > 0: st.info(f"🧮 **Auto-Fare:** {actual_adults} Adult + {child_tix} Child/Half = **₹{calc_fare}**")
                fare_amt = st.number_input("Total Fare Amount (₹)", min_value=0.0, step=5.0, value=float(calc_fare))
                
                acc_opts = get_clean_accounts()
                fare_acc = st.selectbox("Pay From", acc_opts, index=acc_opts.index("MB") if "MB" in acc_opts else 0, key="dyn_fare_acc")
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("🟢 Start Journey", key="start_dyn", use_container_width=True, type="primary"):
                    if not dyn_next_stop or str(dyn_next_stop).strip() == "": st.error("⚠️ Please specify the next stop!")
                    elif not dyn_move or str(dyn_move).strip() == "": st.error("⚠️ Please specify travel mode!")
                    else:
                        try:
                            time_now = get_ist_now()
                            loc_date_str, money_date_str, time_str = time_now.strftime("%d.%m.%y"), time_now.strftime("%d-%m-%Y"), time_now.strftime("%H:%M")
                            
                            sh.worksheet("LOCATION_DATA").append_row([loc_date_str, time_str, dyn_move, "", dyn_people, f"Started Route: {selected_route} towards {dyn_next_stop}"])
                            
                            if fare_amt > 0:
                                start_p = current_loc if current_loc else "Unknown"
                                sh.worksheet("MONEY_DATA").append_row([money_date_str, time_str, "", fare_amt, fare_acc, "Salary", "PERS", "VISIT", selected_route, f"{dyn_move} ({start_p} - {dyn_next_stop})", start_p, start_p, f"with {dyn_people}" if dyn_people != "I" else ""])
                                load_money_data.clear()
                            
                            load_location_data.clear()
                            st.session_state.update(route_active=True, route_type="Dynamic", active_route=selected_route, last_used_route=selected_route, current_move=dyn_move, current_people=dyn_people, target_destination=dyn_next_stop)
                            st.success(f"Started journey to {dyn_next_stop}!")
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

            with c_btn2:
                if st.button("🚶‍♂️ Move Inside Complex", key="internal_dyn", use_container_width=True):
                    if not dyn_next_stop or str(dyn_next_stop).strip() == "": st.error("⚠️ Please specify the next stop!")
                    elif not dyn_move or str(dyn_move).strip() == "": st.error("⚠️ Please specify travel mode!")
                    else:
                        try:
                            time_now = get_ist_now()
                            loc_date_str, money_date_str, time_str = time_now.strftime("%d.%m.%y"), time_now.strftime("%d-%m-%Y"), time_now.strftime("%H:%M")
                            
                            sh.worksheet("LOCATION_DATA").append_row([loc_date_str, time_str, dyn_move, selected_route, dyn_people, f"Started Route: {selected_route} towards {dyn_next_stop}"])
                            
                            if fare_amt > 0:
                                start_p = current_loc if current_loc else "Unknown"
                                sh.worksheet("MONEY_DATA").append_row([money_date_str, time_str, "", fare_amt, fare_acc, "Salary", "PERS", "VISIT", selected_route, f"{dyn_move} ({start_p} - {dyn_next_stop})", start_p, start_p, f"with {dyn_people}" if dyn_people != "I" else ""])
                                load_money_data.clear()
                            
                            load_location_data.clear()
                            st.session_state.update(route_active=True, route_type="Dynamic", active_route=selected_route, last_used_route=selected_route, current_move=dyn_move, current_people=dyn_people, target_destination=dyn_next_stop)
                            st.success(f"Moving towards {dyn_next_stop}!")
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                
        else:
            active_r, active_m, active_p, target_dest = st.session_state.get('active_route', ""), st.session_state.get('current_move', 'Transit'), st.session_state.get('current_people', 'I'), st.session_state.get('target_destination', 'Destination')
            st.success(f"🚲 Journey in progress... ({active_m} with {active_p} towards {target_dest})")

            out_of_route_arr = st.checkbox("📍 Diverted to a different place?")
            if out_of_route_arr:
                dyn_place_sel = st.selectbox("Actual Arrival Place", all_places_list + ["-- Type New --"])
                dyn_place = st.text_input("Type New Place Name") if dyn_place_sel == "-- Type New --" else dyn_place_sel
            else:
                places_for_route = location_logic.get(active_r, [])
                if target_dest not in places_for_route: places_for_route.insert(0, target_dest)
                dyn_place = st.selectbox("Confirm Arrival Place", places_for_route, index=places_for_route.index(target_dest), key="dyn_arrive")
            
            if st.button(f"🛑 Log Arrival at chosen place", key="log_dyn", use_container_width=True, type="primary"):
                if not dyn_place or str(dyn_place).strip() == "": st.error("⚠️ Please specify your arrival place!")
                else:
                    try:
                        time_now = get_ist_now()
                        arr_remark, final_arr_people = "Logged Arrival", active_p
                        
                        if dyn_place == "Girishmore Bus Stop" and "Suborno" in active_p: arr_remark = "Waiting for School Bus"
                        elif dyn_place == "HOME": 
                            final_arr_people = get_home_occupants(active_p)
                            st.session_state.current_people = "I"
                            
                        sh.worksheet("LOCATION_DATA").append_row([time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), "- Stationary -", dyn_place, final_arr_people, arr_remark])
                        load_location_data.clear()
                        st.session_state.update(route_active=False, route_type=None, target_destination="")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    # ==========================================
    # QUICK STOP EXPANDER (ALWAYS AVAILABLE)
    # ==========================================
    with st.expander("⏸️ Quick Stop (Log interactions)", expanded=st.session_state.get('stop_active', False)):
        if not st.session_state.get('stop_active', False):
            if st.button("⏸️ Start Quick Stop", use_container_width=True):
                st.session_state.stop_active = True
                st.session_state.stop_start_time = get_ist_now()
                st.rerun()
        else:
            time_now, start_t = get_ist_now(), st.session_state.stop_start_time
            running_minutes = int((time_now - start_t).total_seconds()) // 60
            
            st.warning(f"⏱️ Stop in progress since {start_t.strftime('%H:%M')} ({running_minutes} min so far)...")
            stop_task = st.selectbox("Select Reason", ["Urine", "Call receive", "Call", "Meet", "-- Type New --"])
            if stop_task == "-- Type New --": stop_task = st.text_input("Type specific reason")
            
            contact_name = ""
            if stop_task in ["Call receive", "Call", "Meet"]:
                df_names = load_people_names()
                people_list = ["-- Select Name --", "-- Type New --"]
                if not df_names.empty and 'Name' in df_names.columns: people_list.extend([str(n).strip() for n in df_names['Name'].dropna() if str(n).strip() != ""])
                sel_name = st.selectbox("Contact Name", people_list)
                if sel_name == "-- Type New --": contact_name = st.text_input("Type New Name")
                elif sel_name != "-- Select Name --": contact_name = sel_name

            btn_label = "▶️ Save & Resume Journey" if st.session_state.route_active else "💾 Save Quick Stop"
            if st.button(btn_label, type="primary", use_container_width=True):
                if stop_task:
                    try:
                        time_now_stop = get_ist_now()
                        today_str, today_people_str = time_now_stop.strftime("%d.%m.%y"), time_now_stop.strftime("%d-%m-%Y")
                        
                        duration_secs = int((time_now_stop - start_t).total_seconds())
                        hours, rem = divmod(duration_secs, 3600)
                        mins, secs = divmod(rem, 60)
                        
                        stop_desc = f"Quick Stop: {stop_task}" + (f" ({contact_name})" if contact_name else "")
                        loc = f"On the way ({st.session_state.get('active_route', '')})" if st.session_state.route_active else (current_loc or "On the way")
                            
                        sh.worksheet("LOCATION_DATA").append_row([today_str, start_t.strftime("%H:%M"), "- Stationary -", loc, st.session_state.current_people, stop_desc])
                        
                        if st.session_state.route_active:
                            sh.worksheet("LOCATION_DATA").append_row([today_str, time_now_stop.strftime("%H:%M"), st.session_state.get('current_move', 'Transit'), "", st.session_state.get('current_people', 'I'), f"Resumed Route: {st.session_state.get('active_route', '')} towards {st.session_state.get('target_destination', '')}"])
                            
                        if contact_name and stop_task in ["Call receive", "Call", "Meet"]:
                            sh_people.worksheet("People Interaction").append_row([contact_name, stop_task, today_people_str, start_t.strftime("%H:%M"), time_now_stop.strftime("%H:%M"), f"{hours:02d}:{mins:02d}:{secs:02d}", "⚠️ INCOMPLETE"])
                            load_interactions.clear()

                        load_location_data.clear()
                        st.session_state.update(stop_active=False, stop_start_time=None)
                        st.success("Stop saved!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                else: st.error("Please provide a reason.")
        
        df_int = load_interactions()
        if not df_int.empty and 'Purpose / Topic' in df_int.columns:
            inc_interactions = df_int[df_int['Purpose / Topic'] == '⚠️ INCOMPLETE']
            if not inc_interactions.empty:
                st.divider()
                st.error(f"⚠️ You have {len(inc_interactions)} incomplete People Interactions!")
                try:
                    int_ws = sh_people.worksheet("People Interaction")
                    for idx, row in inc_interactions.iterrows():
                        sheet_row = idx + 2
                        start_time_val, end_time_val = row.get('Start Time', row.get('Time', '')), row.get('End Time', '')
                        
                        st.markdown(f"**{row.get('Interaction', 'Interaction')}: {row.get('People', 'Unknown')}** | Date: {row.get('Date', '')} | Time: {f'{start_time_val} to {end_time_val}' if end_time_val else start_time_val} | Dur: {row.get('Duration', '')}")
                        
                        c_int1, c_int2 = st.columns([3, 1])
                        with c_int1: new_topic = st.text_input("Purpose / Topic", key=f"topic_{idx}", label_visibility="collapsed")
                        with c_int2:
                            if st.button("Save", key=f"save_topic_{idx}", type="primary"):
                                if new_topic.strip():
                                    try:
                                        int_ws.update_cell(sheet_row, int_ws.row_values(1).index('Purpose / Topic') + 1, new_topic)
                                        load_interactions.clear()
                                        st.success("Updated!")
                                        st.rerun()
                                    except Exception as e: st.error(f"Error: {e}")
                                else: st.warning("Enter Topic")
                except Exception as e: st.warning("⏳ Google Sheets API busy. Please wait.")

    # ==========================================
    # EXPRESS ROUTE EXPANDER
    # ==========================================
    with st.expander("🏫 Express School Route", expanded=False):
        if not st.session_state.route_active:
            col1, col2 = st.columns(2)
            with col1: express_move = st.selectbox("Travel Mode", ["BIKE", "WALK", "BIKE + WALK", "TOTO", "TRAIN"], key="exp_move")
            with col2:
                people_opts = get_list("People")
                if not people_opts: people_opts = ["I", "I, BKP, TKM", "I, TKM"]
                if "I" not in people_opts: people_opts.insert(0, "I")
                express_people = st.selectbox("Companions", people_opts, index=people_opts.index(st.session_state.current_people) if st.session_state.current_people in people_opts else 0, key="exp_people")
                
            if st.button("🟢 Start Express Journey", use_container_width=True):
                try:
                    time_now = get_ist_now()
                    sh.worksheet("LOCATION_DATA").append_row([time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), express_move, "", express_people, "Started Express Route"])
                    load_location_data.clear()
                    st.session_state.update(route_active=True, route_type="Express", current_people=express_people, current_move=express_move, retro_time=get_ist_now().time())
                    st.rerun() 
                except Exception as e: st.error(f"Error: {e}")
        else:
            st.success("🚲 Express Journey in progress...")
            express_place = st.selectbox("Where did you arrive?", ["Karim Da's House (Keys)", "Bhagyabantapur Primary School", "Girishmore Bus Stop", "HOME"])
            
            forgot_keys_fwd, forgot_keys_ret, forgot_bus = False, False, False
            if express_place == "Bhagyabantapur Primary School":
                forgot_keys_fwd = st.checkbox("⚠️ I forgot to log Karim Da's House (Keys) on the way")
                if forgot_keys_fwd: missed_time_fwd = st.time_input("Time you picked up the keys?", value=st.session_state.retro_time, step=60, key="fwd_keys")
            if express_place == "HOME":
                forgot_keys_ret = st.checkbox("⚠️ I forgot to log Karim Da's House (Keys)")
                if forgot_keys_ret: missed_time_keys = st.time_input("Time you dropped the keys?", value=st.session_state.retro_time, step=60, key="ret_keys")
                forgot_bus = st.checkbox("⚠️ I forgot to log Girishmore Bus Stop")
                if forgot_bus: missed_time_bus = st.time_input("Time you stopped at Girishmore?", value=st.session_state.retro_time, step=60, key="ret_bus")
            
            if st.button("🛑 Log Express Arrival", use_container_width=True, type="primary"):
                try:
                    time_now = get_ist_now()
                    today_str, arr_people, trav_mode = time_now.strftime("%d.%m.%y"), st.session_state.current_people, st.session_state.current_move
                    
                    if forgot_keys_fwd and express_place == "Bhagyabantapur Primary School":
                        m_time_str = missed_time_fwd.strftime("%H:%M")
                        sh.worksheet("LOCATION_DATA").append_rows([[today_str, m_time_str, "- Stationary -", "Karim Da's House (Keys)", arr_people, "Retroactive arrival"], [today_str, m_time_str, trav_mode, "", arr_people, "Retroactive transit"]])
                    if express_place == "HOME":
                        if forgot_keys_ret:
                            m_time_k = missed_time_keys.strftime("%H:%M")
                            sh.worksheet("LOCATION_DATA").append_rows([[today_str, m_time_k, "- Stationary -", "Karim Da's House (Keys)", arr_people, "Retroactive arrival"], [today_str, m_time_k, trav_mode, "", arr_people, "Retroactive transit"]])
                        if forgot_bus:
                            m_time_b = missed_time_bus.strftime("%H:%M")
                            sh.worksheet("LOCATION_DATA").append_rows([[today_str, m_time_b, "- Stationary -", "Girishmore Bus Stop", arr_people, "Retroactive arrival"], [today_str, m_time_b, trav_mode, "", "I", "Retroactive transit"]])
                            arr_people = "I"
                    
                    arr_rem = "Waiting for School Bus" if express_place == "Girishmore Bus Stop" and "Suborno" in arr_people else "Logged Arrival"
                    if express_place == "HOME": 
                        arr_people = get_home_occupants(arr_people)
                        st.session_state.current_people = "I"
                        
                    sh.worksheet("LOCATION_DATA").append_row([today_str, time_now.strftime("%H:%M"), "- Stationary -", express_place, arr_people, arr_rem])
                    load_location_data.clear()
                    st.session_state.update(route_active=False, route_type=None, retro_time=get_ist_now().time())
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    st.divider()

    st.markdown("### ⚡ Quick Actions")
    st.markdown('<div class="green-btn-hook"></div>', unsafe_allow_html=True)
    st.markdown("""
        <style>
        div:has(.green-btn-hook) + div + div button { background-color: #28a745 !important; color: white !important; border-color: #28a745 !important; }
        div:has(.green-btn-hook) + div + div button:hover { background-color: #218838 !important; border-color: #1e7e34 !important; }
        </style>
    """, unsafe_allow_html=True)

    def cb_board_bus():
        try:
            time_now = get_ist_now()
            sh.worksheet("LOCATION_DATA").append_row([time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), "- Stationary -", "Girishmore Bus Stop", "I", "Suborno boarded bus to school"])
            st.session_state.update(current_people="I", dyn_people="I", exp_people="I")
            load_location_data.clear()
        except Exception as e: st.session_state.quick_err = str(e)

    def cb_receive_suborno():
        try:
            time_now = get_ist_now()
            new_people = st.session_state.current_people + ", Suborno" if st.session_state.current_people else "I, Suborno"
            sh.worksheet("LOCATION_DATA").append_row([time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), "- Stationary -", "Girishmore Bus Stop", new_people, "Received Suborno from school bus"])
            st.session_state.update(current_people=new_people, dyn_people=new_people, exp_people=new_people)
            load_location_data.clear()
        except Exception as e: st.session_state.quick_err = str(e)

    if "quick_err" in st.session_state:
        st.error(f"Google Sheets Error: {st.session_state.quick_err}")
        del st.session_state.quick_err

    time_now_for_btn = get_ist_now()
    if current_loc == "Girishmore Bus Stop" and "Suborno" in st.session_state.current_people and not st.session_state.route_active and (time_now_for_btn.hour == 8):
        if st.button("🚌 Suborno Boarded Bus", use_container_width=True, type="primary", on_click=cb_board_bus):
            st.success("Logged Suborno boarding bus. You are now traveling alone.")

    if current_loc == "Girishmore Bus Stop" and "Suborno" not in st.session_state.current_people and not st.session_state.route_active and (13 <= time_now_for_btn.hour <= 16):
        if st.button("👦 Received Suborno from Bus", use_container_width=True, type="primary", on_click=cb_receive_suborno):
            st.success("Logged Suborno arriving! Companions updated.")
            
    # --- EXPANDABLE MANUAL LOCATION LOG ---
    with st.expander("📝 Manual Location Log", expanded=False):
        location_logic = get_location_logic()
        loc_date = st.date_input("Log Date", value=st.session_state.locked_date)
        loc_time_str = st.text_input("Start Time (Type in 24hr format)", value=st.session_state.locked_time.strftime("%H:%M"))
        
        col1, col2 = st.columns(2)
        with col1: move = st.selectbox("Move Type", ["- Stationary -"] + get_list("Moves"))
        with col2:
            area_options = ["- Select Area -", "- On the way -"] + list(location_logic.keys())
            area = st.selectbox("Select Route / Area", area_options)
        
        if area == "- On the way -":
            specific_place = ""
            st.info("🚲 Transit log.")
        elif area == "- Select Area -": specific_place = ""
        else:
            specific_place_options = location_logic.get(area, []) + ["-- Type New --"]
            specific_place_sel = st.selectbox("Specific Place", specific_place_options)
            specific_place = st.text_input("Type New Place Name") if specific_place_sel == "-- Type New --" else specific_place_sel

        manual_people_opts = get_list("People")
        if not manual_people_opts: manual_people_opts = ["I"]
        if "I" not in manual_people_opts: manual_people_opts.insert(0, "I")
        
        people = st.selectbox("People", manual_people_opts, index=manual_people_opts.index(st.session_state.current_people) if st.session_state.current_people in manual_people_opts else 0)
        loc_remark = st.text_input("Location Remark (Optional)")
        
        if st.button("💾 Save Manual Entry", use_container_width=True):
            try:
                try: parsed_time = datetime.strptime(loc_time_str.strip(), "%H:%M").strftime("%H:%M")
                except ValueError: st.error("⚠️ Invalid time! Use HH:MM format."); st.stop()
                
                final_move = "" if move == "- Stationary -" else move
                sh.worksheet("LOCATION_DATA").append_row([loc_date.strftime("%d.%m.%y"), parsed_time, final_move, specific_place, people, loc_remark])
                load_location_data.clear()
                
                if specific_place.strip().upper() == "HOME" and move == "- Stationary -": st.session_state.current_people = "I"
                    
                st.success("Logged successfully!")
                st.session_state.update(locked_date=get_ist_now().date(), locked_time=get_ist_now().time())
            except Exception as e: st.error(f"Error saving to Google Sheets: {e}")

# ==========================================
# TAB 2: DATA CONFIG
# ==========================================
with tab_config:
    st.header("⚙️ Data Configuration")
    
    with st.expander("📝 Location Data Entry", expanded=True):
        ld_place_opts = all_places_list + ["-- Type New --"]
        ld_place_sel = st.selectbox("Select Place", ld_place_opts, index=ld_place_opts.index(current_loc) if current_loc in ld_place_opts else 0, key="ld_place_cfg")
        ld_place = st.text_input("Type New Place Name", key="ld_new_place_cfg") if ld_place_sel == "-- Type New --" else ld_place_sel
        
        ld_type = st.selectbox("Entry Type", ["Closed", "-- Type New --"], key="ld_type_cfg")
        
        if ld_type == "Closed":
            ld_final_remark = f"Closed: {get_ist_now().strftime('%A')}"
            st.info(f"📍 Will log: **{ld_final_remark}** (Auto-detected weekday)")
        else: ld_final_remark = st.text_input("Type New Entry (e.g. Purpose of visit)", key="ld_custom_remark_cfg")
        
        if st.button("💾 Save Location Entry", type="primary", use_container_width=True, key="ld_save_btn_cfg"):
            if ld_place and ld_final_remark:
                try:
                    time_now = get_ist_now()
                    sh.worksheet("LOCATION_DATA").append_row([time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), "- Stationary -", ld_place, st.session_state.current_people, ld_final_remark])
                    load_location_data.clear()
                    st.success(f"Saved: {ld_place} -> {ld_final_remark}")
                except Exception as e: st.error(f"Error: {e}")
            else: st.warning("Please provide an entry to save.")

    with st.expander("🕒 Working Hours Entry", expanded=True):
        wh_place_opts = all_places_list + ["-- Type New --"]
        wh_place_sel = st.selectbox("Select Place", wh_place_opts, index=wh_place_opts.index(current_loc) if current_loc in wh_place_opts else 0, key="wh_place_cfg")
        wh_place = st.text_input("Type New Place Name", key="wh_new_place_cfg") if wh_place_sel == "-- Type New --" else wh_place_sel
        
        wh_day_opts = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "All Days", "Mon-Fri", "Sat-Sun"]
        curr_day = get_ist_now().strftime('%A')
        wh_day = st.selectbox("Day(s)", wh_day_opts, index=wh_day_opts.index(curr_day) if curr_day in wh_day_opts else 0, key="wh_day_cfg")

        wh_c1, wh_c2 = st.columns(2)
        with wh_c1: wh_open = st.time_input("Open Time", value=datetime.strptime("09:00", "%H:%M").time(), key="wh_open_cfg")
        with wh_c2: wh_close = st.time_input("Close Time", value=datetime.strptime("17:00", "%H:%M").time(), key="wh_close_cfg")
        
        add_break = st.checkbox("➕ Add Break / Lunch Time", key="wh_break_cfg")
        if add_break:
            b_c1, b_c2 = st.columns(2)
            with b_c1: wh_b_start = st.time_input("Break Start", value=datetime.strptime("14:00", "%H:%M").time(), key="wh_b_start_cfg")
            with b_c2: wh_b_end = st.time_input("Break End", value=datetime.strptime("14:30", "%H:%M").time(), key="wh_b_end_cfg")
        
        if st.button("💾 Save Working Hours", type="primary", use_container_width=True, key="wh_save_btn_cfg"):
            if wh_place:
                try:
                    try:
                        wh_sheet = sh.worksheet("WORKING_HOURS")
                        if "Break_Start" not in wh_sheet.row_values(1):
                            wh_sheet.update_cell(1, 5, "Break_Start")
                            wh_sheet.update_cell(1, 6, "Break_End")
                    except gspread.exceptions.WorksheetNotFound:
                        wh_sheet = sh.add_worksheet(title="WORKING_HOURS", rows="100", cols="6")
                        wh_sheet.append_row(["Place", "Day", "Open", "Close", "Break_Start", "Break_End"])
                    
                    wh_sheet.append_row([wh_place, wh_day, wh_open.strftime("%H:%M"), wh_close.strftime("%H:%M"), wh_b_start.strftime("%H:%M") if add_break else "", wh_b_end.strftime("%H:%M") if add_break else ""])
                    load_working_hours.clear()
                    st.success(f"Saved Working Hours for {wh_place} on {wh_day}")
                except Exception as e: st.error(f"Error: {e}")
