import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="SK Ecosystem", page_icon="📱", layout="centered")

# Helper: Get current IST Time (UTC + 5:30)
def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

# Initialize session state for the Express Tracker
if 'route_active' not in st.session_state:
    st.session_state.route_active = False
if 'current_people' not in st.session_state:
    st.session_state.current_people = "I"

# Connect to Google Sheets
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    client = gspread.authorize(creds)
    return client.open("sk_money_location")

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    st.stop()

# Load Configuration Data (Cached for 10 minutes)
@st.cache_data(ttl=600)
def load_config():
    worksheet = sh.worksheet("CONFIG")
    data = worksheet.get_all_values()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data[1:], columns=data[0])

config_df = load_config()

# Helper: Get clean lists from CONFIG
def get_list(column_name):
    if column_name in config_df.columns:
        return [val.strip() for val in config_df[column_name].dropna().tolist() if val.strip() != ""]
    return []

# Helper: Build Area -> Specific Place dictionary
def get_location_logic():
    logic = {}
    if 'Area' in config_df.columns and 'Specific_Place' in config_df.columns:
        for index, row in config_df.iterrows():
            area = str(row['Area']).strip()
            place = str(row['Specific_Place']).strip()
            if area and place and area.lower() != 'nan' and place.lower() != 'nan':
                if area not in logic:
                    logic[area] = []
                if place not in logic[area]:
                    logic[area].append(place)
    return logic

# Helper: Get Current Location for Smart Pre-fill
def get_current_location():
    try:
        loc_records = sh.worksheet("LOCATION_DATA").get_all_records()
        if loc_records:
            last_record = loc_records[-1] 
            if last_record.get('Move') in ["", "- Stationary -"]:
                return last_record.get('Place')
    except Exception:
        return None
    return None

# ==========================================
# APP LAYOUT & TABS
# ==========================================
st.title("📱 SK Ecosystem")

tab_money, tab_location, tab_dash, tab_help = st.tabs(["💰 Money", "📍 Location", "📊 Dashboard", "📖 Help"])

# ==========================================
# TAB 1: MONEY ENTRY FORM (Live & Responsive)
# ==========================================
with tab_money:
    st.subheader("Add Financial Record")
    
    current_loc = get_current_location()
    if current_loc:
        st.success(f"📍 Detected Location: **{current_loc}** (Auto-filling TO / FROM)")

    entry_date = st.date_input("Date", get_ist_now().date())
    
    col1, col2 = st.columns(2)
    with col1:
        amount_in = st.number_input("IN (Income/Receive)", min_value=0.0, step=10.0)
        account = st.selectbox("Account", get_list("Accounts"))
        entity = st.selectbox("Entity", get_list("Entities"))
        category = st.selectbox("Category", get_list("Categories"))
        
    with col2:
        amount_out = st.number_input("OUT (Expense/Send)", min_value=0.0, step=10.0)
        sub_cat = st.selectbox("Sub Category", get_list("Sub-Categories"))
        
        particulars_opts = ["-- Type New --"] + get_list("Particulars")
        particulars = st.selectbox("Particulars", particulars_opts)
        if particulars == "-- Type New --":
            particulars = st.text_input("Type New Particulars")
            
        # Smart TO/FROM Logic
        base_to_from_opts = get_list("TO_FROM")
        to_from_opts = ["-- Type New --"] + base_to_from_opts
        default_index = 0
        
        if current_loc:
            if current_loc not in to_from_opts:
                to_from_opts.insert(1, current_loc)
                default_index = 1
            else:
                default_index = to_from_opts.index(current_loc)
        
        to_from = st.selectbox("TO / FROM", to_from_opts, index=default_index)
        if to_from == "-- Type New --":
            to_from = st.text_input("Type New TO / FROM")

    remark = st.text_input("Remark (Optional)")
    
    submit_money = st.button("💾 Save Money Entry", use_container_width=True)
    
    if submit_money:
        try:
            formatted_date = entry_date.strftime("%d-%m-%Y")
            row_data = [
                formatted_date, 
                amount_in if amount_in > 0 else "", 
                amount_out if amount_out > 0 else "", 
                account, entity, category, sub_cat, particulars, to_from, remark
            ]
            sh.worksheet("MONEY_DATA").append_row(row_data)
            st.success(f"Saved: ₹{amount_in if amount_in > 0 else amount_out} logged to {to_from}!")
        except Exception as e:
            st.error(f"Failed to save: {e}")

# ==========================================
# TAB 2: LOCATION ENTRY FORM
# ==========================================
with tab_location:
    
    # --- 🚀 EXPRESS SCHOOL ROUTE TRACKER ---
    st.markdown("### 🏫 Express School Route")
    
    express_container = st.container(border=True)
    with express_container:
        if not st.session_state.route_active:
            # STATE: READY TO START
            st.write("Ready to leave?")
            col1, col2 = st.columns(2)
            with col1:
                express_move = st.selectbox("Travel Mode", ["BIKE", "WALK", "BIKE + WALK", "TOTO"], key="exp_move")
            with col2:
                people_opts = get_list("People")
                if not people_opts: 
                    people_opts = ["I", "I, BKP, TKM", "I, TKM"]
                express_people = st.selectbox("Companions", people_opts, key="exp_people")
                
            if st.button("🟢 Start Journey", use_container_width=True):
                try:
                    time_now = get_ist_now()
                    row_data = [
                        time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), 
                        express_move, "", express_people, "Started Express Route"
                    ]
                    sh.worksheet("LOCATION_DATA").append_row(row_data)
                    
                    st.session_state.route_active = True
                    st.session_state.current_people = express_people
                    st.rerun() 
                except Exception as e:
                    st.error(f"Error: {e}")
                        
        else:
            # STATE: JOURNEY IN PROGRESS
            st.success("🚲 Journey in progress...")
            
            express_place = st.selectbox(
                "Where did you arrive?", 
                ["Karim Da's House (Keys)", "Bhagyabantapur Primary School", "Girishmore Bus Stop", "HOME"]
            )
            
            forgot_keys = False
            forgot_bus = False
            
            if express_place == "Bhagyabantapur Primary School":
                forgot_keys = st.checkbox("⚠️ I forgot to log Karim Da's House (Keys) on the way")
                if forgot_keys:
                    missed_time = st.time_input("Time you picked up the keys?", get_ist_now().time(), step=60)
            
            if express_place == "HOME":
                forgot_bus = st.checkbox("⚠️ I forgot to log Girishmore Bus Stop on the way back")
                if forgot_bus:
                    missed_time = st.time_input("Time you stopped at Girishmore?", get_ist_now().time(), step=60)
            
            if st.button("🛑 Log Arrival", use_container_width=True, type="primary"):
                try:
                    time_now = get_ist_now()
                    today_str = time_now.strftime("%d.%m.%y")
                    arrival_people = st.session_state.current_people
                    
                    # 1. Log Missed Keys
                    if forgot_keys and express_place == "Bhagyabantapur Primary School":
                        missed_row = [
                            today_str, missed_time.strftime("%H:%M"), 
                            "- Stationary -", "Karim Da's House (Keys)", arrival_people, "Retroactive log"
                        ]
                        sh.worksheet("LOCATION_DATA").append_row(missed_row)
                    
                    # 2. Log Missed Bus Stop
                    if forgot_bus and express_place == "HOME":
                        missed_row = [
                            today_str, missed_time.strftime("%H:%M"), 
                            "- Stationary -", "Girishmore Bus Stop", arrival_people, "Retroactive log"
                        ]
                        sh.worksheet("LOCATION_DATA").append_row(missed_row)
                        arrival_people = "I" # Assume you dropped them off
                    
                    # 3. Log Final Arrival
                    arr_row = [
                        today_str, time_now.strftime("%H:%M"), 
                        "- Stationary -", express_place, arrival_people, ""
                    ]
                    sh.worksheet("LOCATION_DATA").append_row(arr_row)
                    
                    st.session_state.route_active = False
                    st.session_state.current_people = "I"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()

    # --- 📝 STANDARD MANUAL LOG (Live & Responsive) ---
    st.markdown("### 📝 Manual Location Log")
    location_logic = get_location_logic()

    loc_date = st.date_input("Log Date", get_ist_now().date())
    loc_time = st.time_input("Start Time", get_ist_now().time(), step=60)
    
    col1, col2 = st.columns(2)
    with col1:
        move_opts = ["- Stationary -"] + get_list("Moves")
        move = st.selectbox("Move Type", move_opts)
        
    with col2:
        area_options = ["- Select Area -", "- On the way -"] + list(location_logic.keys())
        area = st.selectbox("Select Route / Area", area_options)
    
    if area == "- On the way -":
        specific_place = ""
        st.info("🚲 You are in transit. No specific place needed.")
    elif area == "- Select Area -":
        specific_place = ""
    else:
        specific_place_options = location_logic.get(area, []) + ["-- Type New --"]
        specific_place = st.selectbox("Specific Place", specific_place_options)
        if specific_place == "-- Type New --":
            specific_place = st.text_input("Type New Place Name")

    people_opts = ["- Alone -"] + get_list("People")
    people = st.selectbox("People", people_opts)
    
    loc_remark = st.text_input("Location Remark (Optional)")
    
    submit_location = st.button("💾 Save Manual Entry", use_container_width=True)
    
    if submit_location:
        try:
            formatted_date = loc_date.strftime("%d.%m.%y")
            formatted_time = loc_time.strftime("%H:%M")
            final_move = "" if move == "- Stationary -" else move
            final_people = "" if people == "- Alone -" else people
            
            row_data = [formatted_date, formatted_time, final_move, specific_place, final_people, loc_remark]
            sh.worksheet("LOCATION_DATA").append_row(row_data)
            
            if final_move:
                st.success(f"Logged Transit: {final_move} at {formatted_time}")
            else:
                st.success(f"Logged Arrival: {specific_place} at {formatted_time}")
        except Exception as e:
            st.error(f"Error saving to Google Sheets: {e}")

# ==========================================
# TAB 3: DASHBOARD & TRACKERS
# ==========================================
with tab_dash:
    st.header("📊 Overview")
    
    # --- 1. REIMBURSEMENT TRACKER ---
    try:
        money_records = sh.worksheet("MONEY_DATA").get_all_records()
        df_money = pd.DataFrame(money_records)
        
        if not df_money.empty:
            df_money['In'] = pd.to_numeric(df_money['In'].replace('', 0), errors='coerce').fillna(0)
            df_money['Out'] = pd.to_numeric(df_money['Out'].replace('', 0), errors='coerce').fillna(0)
            
            school_accounts = ["MDM Indian", "MB3 (SCH)", "CASH MB3 (SCH)"]
            df_money['AC_Owner'] = df_money['AC'].apply(lambda x: 'SCH' if x in school_accounts else 'PERS')
            
            pers_paid_for_sch = df_money[(df_money['AC_Owner'] == 'PERS') & (df_money['Entity'] == 'SCH')]['Out'].sum()
            sch_repaid_pers = df_money[(df_money['AC_Owner'] == 'PERS') & (df_money['Entity'] == 'SCH')]['In'].sum()
            school_owes_you = pers_paid_for_sch - sch_repaid_pers
            
            sch_paid_for_pers = df_money[(df_money['AC_Owner'] == 'SCH') & (df_money['Entity'] == 'PERS')]['Out'].sum()
            pers_repaid_sch = df_money[(df_money['AC_Owner'] == 'SCH') & (df_money['Entity'] == 'PERS')]['In'].sum()
            you_owe_school = sch_paid_for_pers - pers_repaid_sch
            
            st.subheader("🔔 Reimbursement Reminders")
            r1, r2 = st.columns(2)
            r1.metric("School Owes You", f"₹ {school_owes_you:,.2f}")
            r2.metric("You Owe School", f"₹ {you_owe_school:,.2f}")
            
            st.divider()
            
            st.subheader("🗂️ Expense Logs")
            log_pers, log_sch = st.tabs(["👤 Personal", "🏫 School"])
            
            with log_pers:
                df_pers = df_money[(df_money['Entity'] == 'PERS') & (df_money['Out'] > 0)]
                st.dataframe(df_pers[['Date', 'AC', 'Category', 'Particulars', 'Out']], use_container_width=True, hide_index=True)
                
            with log_sch:
                df_sch = df_money[(df_money['Entity'] == 'SCH') & (df_money['Out'] > 0)]
                st.dataframe(df_sch[['Date', 'AC', 'Category', 'Particulars', 'Out']], use_container_width=True, hide_index=True)
        else:
            st.info("No financial data available yet.")
    except Exception as e:
        st.error(f"Could not load money dashboard: {e}")

    st.divider()

    # --- 2. LOCATION DURATION LOG ---
    st.subheader("⏱️ Today's Location Log")
    try:
        loc_records = sh.worksheet("LOCATION_DATA").get_all_records()
        df_loc = pd.DataFrame(loc_records)
        
        if not df_loc.empty:
            latest_date = df_loc['Date'].iloc[-1]
            df_today = df_loc[df_loc['Date'] == latest_date].copy()
            
            df_today['Time_Obj'] = pd.to_datetime(df_today['Time'], format='%H:%M', errors='coerce')
            time_diffs = df_today['Time_Obj'].shift(-1) - df_today['Time_Obj']
            
            def format_duration(td):
                if pd.isnull(td):
                    return "Current"
                total_seconds = int(td.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                return f"{hours}:{minutes:02d}"

            df_today['Duration'] = time_diffs.apply(format_duration)
            display_cols = ['Time', 'Duration', 'Move', 'Place', 'People', 'Remark']
            st.dataframe(df_today[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No location logs found yet.")
    except Exception as e:
        st.error(f"Could not load location dashboard: {e}")

# ==========================================
# TAB 4: INSTRUCTIONS & MANUAL
# ==========================================
with tab_help:
    st.header("📖 User Manual")
    with st.expander("🛠️ 1. The CONFIG Tab"):
        st.write("Ensure your Google Sheet 'CONFIG' tab has these exact headers in Row 1:")
        st.code("Accounts, Entities, Categories, Sub-Categories, Particulars, TO_FROM, Remarks, Moves, Places, People, Area, Specific_Place")
        
    with st.expander("💰 2. Money Entry Rules"):
        st.markdown("""
        **AC = Whose money physically moved? | Entity = Whose expense is it actually?**
        - **Using personal money for school:** AC = `MB`, Entity = `SCH`. Result: School owes you.
        - **Using school money for personal:** AC = `MB3 (SCH)`, Entity = `PERS`. Result: You owe school.
        """)

    with st.expander("📍 3. Location Rules"):
        st.markdown("""
        - **Express Route:** Click Start when leaving. Click Stop when you arrive. Use checkboxes if you forgot intermediate stops.
        - **Manual Log:** Select `- On the way -` for transit. Select an area for specific arrivals. 
        """)
