import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="Location Express & Logs", page_icon="⚡", layout="centered")

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

# Initialize Session States needed for these modules
if 'route_active' not in st.session_state: st.session_state.route_active = False
if 'route_type' not in st.session_state: st.session_state.route_type = None 
if 'current_people' not in st.session_state: st.session_state.current_people = "I"
if 'current_move' not in st.session_state: st.session_state.current_move = "BIKE"
if 'retro_time' not in st.session_state: st.session_state.retro_time = get_ist_now().time()
if 'locked_date' not in st.session_state: st.session_state.locked_date = get_ist_now().date()
if 'locked_time' not in st.session_state: st.session_state.locked_time = get_ist_now().time()
if 'stop_active' not in st.session_state: st.session_state.stop_active = False
if 'stop_start_time' not in st.session_state: st.session_state.stop_start_time = None
if 'active_route' not in st.session_state: st.session_state.active_route = ""
if 'target_destination' not in st.session_state: st.session_state.target_destination = ""

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
def load_people_names():
    try: return pd.DataFrame(sh_people.worksheet("People").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_interactions():
    try: return pd.DataFrame(sh_people.worksheet("People Interaction").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

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

def get_current_location_details():
    df_loc = load_location_data()
    if not df_loc.empty:
        last_record = df_loc.iloc[-1].to_dict()
        move_val = str(last_record.get('Move', '')).strip()
        if move_val in ["", "- Stationary -", "nan"]:
            loc = str(last_record.get('Place', '')).strip()
            return loc
    return None

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
            
            last_record = df_loc.iloc[-1].to_dict()
            move_val = str(last_record.get('Move','')).strip()
            place_val = str(last_record.get('Place','')).strip().upper()
            
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
st.title("⚡ Location Express & Logs")
current_loc = get_current_location_details()

# ==========================================
# QUICK STOP EXPANDER
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

# ==========================================
# MANUAL LOCATION LOG EXPANDER
# ==========================================
with st.expander("📝 Manual Location Log", expanded=False):
    location_logic = get_location_logic()
    all_places_list = get_list("Places")
    
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
