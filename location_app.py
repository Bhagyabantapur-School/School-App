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
if 'last_used_route' not in st.session_state: st.session_state.last_used_route = None
if 'target_destination' not in st.session_state: st.session_state.target_destination = ""

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    # ONLY CONNECTING TO LOCATION SHEET FOR MAXIMUM SPEED
    return client.open("sk_money_location")

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    st.stop()

# --- CACHING ENGINE ---
@st.cache_data(ttl=600)
def load_config():
    try: return pd.DataFrame(sh.worksheet("CONFIG").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_location_data():
    try: return pd.DataFrame(sh.worksheet("LOCATION_DATA").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_money_data(): 
    try: return pd.DataFrame(sh.worksheet("MONEY_DATA").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_working_hours():
    try: return pd.DataFrame(sh.worksheet("WORKING_HOURS").get_all_records())
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

            last_record = df_loc.iloc[-1].to_dict()
            move_val = str(last_record.get('Move','')).strip()
            place_val = str(last_record.get('Place','')).strip().upper()
            
            # --- Auto-Default to "I" if at HOME ---
            if move_val in ["", "- Stationary -", "nan"] and place_val == "HOME":
                st.session_state.current_people = "I"
            else:
                st.session_state.current_people = str(last_record.get('People', 'I'))
            
            if move_val not in ["", "- Stationary -", "nan"]:
                st.session_state.route_active = True
                rem = str(last_record.get('Remark', ''))
                if "Started Route:" in rem:
                    st.session_state.active_route = rem.split("Started Route:")[-1].split("towards")[0].strip()
                    if "towards" in rem:
                        st.session_state.target_destination = rem.split("towards")[-1].strip()
                    st.session_state.route_type = "Dynamic"
                else:
                    st.session_state.route_type = "Express" 
            else:
                st.session_state.route_active = False
                st.session_state.route_type = None
                
        st.session_state.state_synced = True

sync_journey_state()

# ==========================================
# APP LAYOUT 
# ==========================================
st.title("📍 SK Location Tracker")

# --- LOCATION STATUS & SYNC BUTTON ---
col_stat, col_sync = st.columns([3, 1])
with col_stat:
    current_loc, loc_duration = get_current_location_details()
    if current_loc:
        st.info(f"📍 **Current:** {current_loc} &nbsp;|&nbsp; ⏱️ **Duration:** {loc_duration}")
    else:
        st.info("📍 **Current:** In Transit / Unknown")

with col_sync:
    if st.button("🔄 Sync", use_container_width=True):
        load_location_data.clear()
        if 'state_synced' in st.session_state:
            del st.session_state.state_synced
        st.rerun()

st.divider()

all_places_list = get_list("Places")
if 'target_destination' not in st.session_state: st.session_state.target_destination = ""

# ==========================================
# DYNAMIC AREA ROUTE 
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

st.divider()

# ==========================================
# QUICK ACTIONS
# ==========================================
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
        st.session_state.update(current_people="I")
        load_location_data.clear()
    except Exception as e: st.session_state.quick_err = str(e)

def cb_receive_suborno():
    try:
        time_now = get_ist_now()
        new_people = st.session_state.current_people + ", Suborno" if st.session_state.current_people else "I, Suborno"
        sh.worksheet("LOCATION_DATA").append_row([time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), "- Stationary -", "Girishmore Bus Stop", new_people, "Received Suborno from school bus"])
        st.session_state.update(current_people=new_people)
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
