import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="SK Ecosystem", page_icon="📱", layout="centered")

# Helper: Get current IST Time (UTC + 5:30)
def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

# Initialize session state memories
if 'route_active' not in st.session_state:
    st.session_state.route_active = False
if 'current_people' not in st.session_state:
    st.session_state.current_people = "I"
if 'current_move' not in st.session_state:
    st.session_state.current_move = "BIKE"
if 'retro_time' not in st.session_state:
    st.session_state.retro_time = get_ist_now().time()

# Lock the initial date/time so they don't jump when you click dropdowns
if 'locked_date' not in st.session_state:
    st.session_state.locked_date = get_ist_now().date()
if 'locked_time' not in st.session_state:
    st.session_state.locked_time = get_ist_now().time()

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
# TAB 1: MONEY ENTRY FORM
# ==========================================
with tab_money:
    st.subheader("Add Financial Record")
    
    current_loc = get_current_location()
    if current_loc:
        st.success(f"📍 Detected Location: **{current_loc}** (Auto-filling TO / FROM)")

    entry_date = st.date_input("Date", value=st.session_state.locked_date)
    
    col1, col2 = st.columns(2)
    with col1:
        amount_in = st.number_input("IN (Income/Receive)", min_value=0.0, step=10.0)
        account = st.selectbox("Account", get_list("Accounts"))
        
        # 1. Select Entity
        entity = st.selectbox("Entity", get_list("Entities"))
        
        # 2. Filter Category
        if 'Map_Entity' in config_df.columns:
            ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == entity]
            cat_opts = [c for c in ent_df['Map_Category'].dropna().unique() if str(c).strip() != ""]
            category = st.selectbox("Category", cat_opts + ["-- Type New --"])
            
            if category == "-- Type New --":
                category = st.text_input("Type New Category")
                cat_df = pd.DataFrame() 
            else:
                cat_df = ent_df[ent_df['Map_Category'].astype(str).str.strip() == category]
        else:
            category = st.selectbox("Category", get_list("Categories") + ["-- Type New --"])
            if category == "-- Type New --":
                category = st.text_input("Type New Category")
            cat_df = pd.DataFrame()
            
    with col2:
        amount_out = st.number_input("OUT (Expense/Send)", min_value=0.0, step=10.0)
        
        # 3. Filter Sub-Category
        if not cat_df.empty and 'Map_SubCat' in cat_df.columns:
            sub_opts = [s for s in cat_df['Map_SubCat'].dropna().unique() if str(s).strip() != ""]
            sub_cat = st.selectbox("Sub Category", sub_opts + ["-- Type New --"])
            
            if sub_cat == "-- Type New --":
                sub_cat = st.text_input("Type New Sub Category")
                sub_df = pd.DataFrame()
            else:
                sub_df = cat_df[cat_df['Map_SubCat'].astype(str).str.strip() == sub_cat]
        else:
            sub_cat = st.selectbox("Sub Category", get_list("Sub-Categories") + ["-- Type New --"])
            if sub_cat == "-- Type New --":
                sub_cat = st.text_input("Type New Sub Category")
            sub_df = pd.DataFrame()
        
        # 4. Filter Particulars
        if not sub_df.empty and 'Map_Particular' in sub_df.columns:
            part_opts = [p for p in sub_df['Map_Particular'].dropna().unique() if str(p).strip() != ""]
            particulars = st.selectbox("Particulars", part_opts + ["-- Type New --"])
            
            if particulars == "-- Type New --":
                particulars = st.text_input("Type New Particulars")
                part_df = pd.DataFrame()
            else:
                part_df = sub_df[sub_df['Map_Particular'].astype(str).str.strip() == particulars]
        else:
            particulars = st.selectbox("Particulars", get_list("Particulars") + ["-- Type New --"])
            if particulars == "-- Type New --":
                particulars = st.text_input("Type New Particulars")
            part_df = pd.DataFrame()
            
        # 5. Filter TO / FROM (and combine with Smart Location)
        if not part_df.empty and 'Map_ToFrom' in part_df.columns:
            mapped_tofrom = [t for t in part_df['Map_ToFrom'].dropna().unique() if str(t).strip() != ""]
        else:
            mapped_tofrom = get_list("TO_FROM")
            
        to_from_opts = ["-- Type New --"] + mapped_tofrom
        default_index = 0
        
        # If your phone detects you are at a shop, it overrides the mapped default
        if current_loc:
            if current_loc not in to_from_opts:
                to_from_opts.insert(1, current_loc)
                default_index = 1
            else:
                default_index = to_from_opts.index(current_loc)
        
        to_from = st.selectbox("TO / FROM", to_from_opts, index=default_index)
        
        if to_from == "-- Type New --":
            to_from = st.text_input("Type New TO / FROM")
            tf_df = pd.DataFrame()
        else:
            if not part_df.empty and 'Map_ToFrom' in part_df.columns:
                tf_df = part_df[part_df['Map_ToFrom'].astype(str).str.strip() == to_from]
            else:
                tf_df = pd.DataFrame()

    # 6. Filter Remarks
    if not tf_df.empty and 'Map_Remark' in tf_df.columns:
        rem_opts = [r for r in tf_df['Map_Remark'].dropna().unique() if str(r).strip() != ""]
        remark_box = st.selectbox("Remark", ["- None -"] + rem_opts + ["-- Type New --"])
    else:
        rem_opts = get_list("Remarks")
        remark_box = st.selectbox("Remark", ["- None -"] + rem_opts + ["-- Type New --"])
        
    if remark_box == "-- Type New --":
        remark = st.text_input("Type New Remark")
    elif remark_box == "- None -":
        remark = ""
    else:
        remark = remark_box
    
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
            
            # Reset locked date
            st.session_state.locked_date = get_ist_now().date() 
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
            st.write("Ready to leave?")
            col1, col2 = st.columns(2)
            with col1:
                express_move = st.selectbox("Travel Mode", ["BIKE", "WALK", "BIKE + WALK", "TOTO"], key="exp_move")
            with col2:
                people_opts = get_list("People")
                if not people_opts: 
                    people_opts = ["I", "I, BKP, TKM", "I, TKM"]
                if "I" not in people_opts:
                    people_opts.insert(0, "I")
                default_idx = people_opts.index("I")
                
                express_people = st.selectbox("Companions", people_opts, index=default_idx, key="exp_people")
                
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
                    st.session_state.current_move = express_move
                    st.session_state.retro_time = get_ist_now().time()
                    st.rerun() 
                except Exception as e:
                    st.error(f"Error: {e}")
                        
        else:
            st.success("🚲 Journey in progress...")
            
            express_place = st.selectbox(
                "Where did you arrive?", 
                ["Karim Da's House (Keys)", "Bhagyabantapur Primary School", "Girishmore Bus Stop", "HOME"]
            )
            
            forgot_keys_fwd = False
            forgot_keys_ret = False
            forgot_bus = False
            
            if express_place == "Bhagyabantapur Primary School":
                forgot_keys_fwd = st.checkbox("⚠️ I forgot to log Karim Da's House (Keys) on the way")
                if forgot_keys_fwd:
                    missed_time_fwd = st.time_input("Time you picked up the keys?", value=st.session_state.retro_time, step=60, key="fwd_keys")
            
            if express_place == "HOME":
                st.write("**Missed any stops on the way back?**")
                forgot_keys_ret = st.checkbox("⚠️ I forgot to log Karim Da's House (Keys)")
                if forgot_keys_ret:
                    missed_time_keys = st.time_input("Time you dropped the keys?", value=st.session_state.retro_time, step=60, key="ret_keys")
                    
                forgot_bus = st.checkbox("⚠️ I forgot to log Girishmore Bus Stop")
                if forgot_bus:
                    missed_time_bus = st.time_input("Time you stopped at Girishmore?", value=st.session_state.retro_time, step=60, key="ret_bus")
            
            if st.button("🛑 Log Arrival", use_container_width=True, type="primary"):
                try:
                    time_now = get_ist_now()
                    today_str = time_now.strftime("%d.%m.%y")
                    arrival_people = st.session_state.current_people
                    travel_mode = st.session_state.current_move
                    
                    # 1. Log Missed Keys (FORWARD JOURNEY)
                    if forgot_keys_fwd and express_place == "Bhagyabantapur Primary School":
                        m_time_str = missed_time_fwd.strftime("%H:%M")
                        sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_str, "- Stationary -", "Karim Da's House (Keys)", arrival_people, "Retroactive arrival"])
                        sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_str, travel_mode, "", arrival_people, "Retroactive transit"])
                    
                    # 2. Log Missed Stops (RETURN JOURNEY)
                    if express_place == "HOME":
                        if forgot_keys_ret:
                            m_time_k = missed_time_keys.strftime("%H:%M")
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_k, "- Stationary -", "Karim Da's House (Keys)", arrival_people, "Retroactive arrival"])
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_k, travel_mode, "", arrival_people, "Retroactive transit"])
                        
                        if forgot_bus:
                            m_time_b = missed_time_bus.strftime("%H:%M")
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_b, "- Stationary -", "Girishmore Bus Stop", arrival_people, "Retroactive arrival"])
                            arrival_people = "I" # Dropped them off!
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_b, travel_mode, "", arrival_people, "Retroactive transit"])
                    
                    # 3. Log Final Arrival
                    arr_row = [
                        today_str, time_now.strftime("%H:%M"), 
                        "- Stationary -", express_place, arrival_people, ""
                    ]
                    sh.worksheet("LOCATION_DATA").append_row(arr_row)
                    
                    st.session_state.route_active = False
                    st.session_state.current_people = "I"
                    st.session_state.retro_time = get_ist_now().time()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()

    # --- 📝 STANDARD MANUAL LOG ---
    st.markdown("### 📝 Manual Location Log")
    location_logic = get_location_logic()

    loc_date = st.date_input("Log Date", value=st.session_state.locked_date)
    
    # --- SMART COMBO TIME SELECTOR (1-Minute Intervals) ---
    current_time_str = st.session_state.locked_time.strftime("%H:%M")
    
    # Generate all 1-minute intervals (00:00 to 23:59)
    interval_times = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
    
    time_options = [f"🕒 Current ({current_time_str})", "⌨️ Type Manually..."] + interval_times
    
    selected_time_opt = st.selectbox("Start Time", time_options)
    
    if selected_time_opt == "⌨️ Type Manually...":
        loc_time_str = st.text_input("Type exact time (HH:MM)", value=current_time_str)
    elif selected_time_opt.startswith("🕒 Current"):
        loc_time_str = current_time_str
    else:
        loc_time_str = selected_time_opt
    # -----------------------------------------------------
    
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

    manual_people_opts = get_list("People")
    if not manual_people_opts:
        manual_people_opts = ["I"]
    if "I" not in manual_people_opts:
        manual_people_opts.insert(0, "I")
    manual_default_idx = manual_people_opts.index("I")
    
    people = st.selectbox("People", manual_people_opts, index=manual_default_idx)
    
    loc_remark = st.text_input("Location Remark (Optional)")
    
    submit_location = st.button("💾 Save Manual Entry", use_container_width=True)
    
    if submit_location:
        try:
            # Safely check if the user typed the time correctly
            try:
                parsed_time = datetime.strptime(loc_time_str.strip(), "%H:%M")
                formatted_time = parsed_time.strftime("%H:%M")
            except ValueError:
                st.error("⚠️ Invalid time! Please type the time in HH:MM format (like 08:30 or 15:45).")
                st.stop()
                
            formatted_date = loc_date.strftime("%d.%m.%y")
            final_move = "" if move == "- Stationary -" else move
            
            row_data = [formatted_date, formatted_time, final_move, specific_place, people, loc_remark]
            sh.worksheet("LOCATION_DATA").append_row(row_data)
            
            if final_move:
                st.success(f"Logged Transit: {final_move} at {formatted_time}")
            else:
                st.success(f"Logged Arrival: {specific_place} at {formatted_time}")
                
            # Reset locked values for next entry
            st.session_state.locked_date = get_ist_now().date()
            st.session_state.locked_time = get_ist_now().time()
        except Exception as e:
            st.error(f"Error saving to Google Sheets: {e}")

# ==========================================
# TAB 3: DASHBOARD & TRACKERS
# ==========================================
with tab_dash:
    st.header("📊 Overview")
    
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

            df_today['Duration'] = time_
