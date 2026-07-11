import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="Data Configuration", page_icon="⚙️", layout="centered")

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

if 'current_people' not in st.session_state: st.session_state.current_people = "I"

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
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
def load_working_hours():
    try: return pd.DataFrame(sh.worksheet("WORKING_HOURS").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

def get_current_location_details():
    df_loc = load_location_data()
    if not df_loc.empty:
        last_record = df_loc.iloc[-1].to_dict()
        move_val = str(last_record.get('Move', '')).strip()
        if move_val in ["", "- Stationary -", "nan"]:
            loc = str(last_record.get('Place', '')).strip()
            return loc
    return None

def sync_journey_state():
    df_loc = load_location_data()
    if not df_loc.empty:
        last_rec = df_loc.iloc[-1].to_dict()
        m_val, p_val = str(last_rec.get('Move','')).strip(), str(last_rec.get('Place','')).strip().upper()
        
        if m_val in ["", "- Stationary -", "nan"] and p_val == "HOME": st.session_state.current_people = "I"
        else: st.session_state.current_people = str(last_rec.get('People', 'I'))

sync_journey_state()

# ==========================================
# APP LAYOUT
# ==========================================
st.title("⚙️ Data Configuration")
current_loc = get_current_location_details()
all_places_list = get_list("Places")

# ==========================================
# DATA CONFIGURATION
# ==========================================

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
