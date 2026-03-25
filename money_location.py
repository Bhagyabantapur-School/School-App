import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="SK Ecosystem", page_icon="📱", layout="centered")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

# Initialize session states
if 'route_active' not in st.session_state:
    st.session_state.route_active = False
if 'current_people' not in st.session_state:
    st.session_state.current_people = "I"
if 'current_move' not in st.session_state:
    st.session_state.current_move = "BIKE"
if 'retro_time' not in st.session_state:
    st.session_state.retro_time = get_ist_now().time()
if 'locked_date' not in st.session_state:
    st.session_state.locked_date = get_ist_now().date()
if 'locked_time' not in st.session_state:
    st.session_state.locked_time = get_ist_now().time()

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

@st.cache_data(ttl=600)
def load_config():
    worksheet = sh.worksheet("CONFIG")
    data = worksheet.get_all_values()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data[1:], columns=data[0])

config_df = load_config()

def get_list(column_name):
    if column_name in config_df.columns:
        return [val.strip() for val in config_df[column_name].dropna().tolist() if val.strip() != ""]
    return []

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

def get_shop_type(place_name):
    if 'Specific_Place' in config_df.columns and 'Shop_Type' in config_df.columns:
        match = config_df[config_df['Specific_Place'].astype(str).str.strip() == place_name]
        if not match.empty:
            s_type = match['Shop_Type'].dropna().values
            if len(s_type) > 0 and str(s_type[0]).strip() != "":
                return str(s_type[0]).strip()
    return None

# ==========================================
# APP LAYOUT & TABS
# ==========================================
st.title("📱 SK Ecosystem")

tab_money, tab_shopping, tab_location, tab_dash, tab_help = st.tabs(["💰 Money", "🛒 Shopping", "📍 Location", "📊 Dash", "📖 Help"])

current_loc = get_current_location()
current_shop_type = get_shop_type(current_loc) if current_loc else None

# ==========================================
# TAB 1: MONEY ENTRY FORM (Upgraded with Fund)
# ==========================================
with tab_money:
    st.subheader("Add Financial Record")
    
    if current_loc:
        st.success(f"📍 Detected Location: **{current_loc}**")
        if current_shop_type:
            st.info(f"🛒 **Active Shopping Profile:** {current_shop_type}")

    entry_date = st.date_input("Date", value=st.session_state.locked_date)
    
    col1, col2 = st.columns(2)
    with col1:
        amount_in = st.number_input("IN (Income/Receive)", min_value=0.0, step=10.0)
        account = st.selectbox("Account (Physical)", get_list("Accounts"))
        fund = st.selectbox("Fund (Virtual Source)", get_list("Funds")) # NEW FUND SELECTION
        entity = st.selectbox("Entity", get_list("Entities"))
        
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
            
        if not part_df.empty and 'Map_ToFrom' in part_df.columns:
            mapped_tofrom = [t for t in part_df['Map_ToFrom'].dropna().unique() if str(t).strip() != ""]
        else:
            mapped_tofrom = get_list("TO_FROM")
            
        to_from_opts = ["-- Type New --"] + mapped_tofrom
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
            tf_df = pd.DataFrame()
        else:
            if not part_df.empty and 'Map_ToFrom' in part_df.columns:
                tf_df = part_df[part_df['Map_ToFrom'].astype(str).str.strip() == to_from]
            else:
                tf_df = pd.DataFrame()

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
            # Upgraded row structure: Includes 'fund'
            row_data = [
                formatted_date, 
                amount_in if amount_in > 0 else "", 
                amount_out if amount_out > 0 else "", 
                account, fund, entity, category, sub_cat, particulars, to_from, remark
            ]
            sh.worksheet("MONEY_DATA").append_row(row_data)
            st.success(f"Saved: ₹{amount_in if amount_in > 0 else amount_out} logged to {to_from}!")
            st.session_state.locked_date = get_ist_now().date() 
        except Exception as e:
            st.error(f"Failed to save: {e}")

# ==========================================
# TAB 2: SHOPPING LIST (Location-Aware)
# ==========================================
with tab_shopping:
    st.header("🛒 Smart Shopping List")
    
    if current_shop_type:
        st.success(f"📍 You are at a **{current_shop_type}** shop. Showing your list:")
        try:
            shop_records = sh.worksheet("SHOPPING_LIST").get_all_records()
            df_shop = pd.DataFrame(shop_records)
            
            if not df_shop.empty:
                # Filter for Pending items matching the current shop type
                active_list = df_shop[(df_shop['Status'] == 'Pending') & (df_shop['Shop_Type'] == current_shop_type)]
                
                if not active_list.empty:
                    st.dataframe(active_list[['Item', 'Est_Cost']], use_container_width=True, hide_index=True)
                    st.info("💡 To cross an item off, log the purchase in the 💰 Money tab, then update the sheet later.")
                else:
                    st.write(f"No pending items for {current_shop_type} right now.")
            else:
                st.write("Your shopping list is completely empty.")
        except Exception as e:
            st.error("Could not load shopping list.")
    else:
        st.write("You are not currently at a mapped shop. Here you can add items for later.")
    
    st.divider()
    st.subheader("➕ Add New Item to List")
    
    with st.form("add_shop_item", clear_on_submit=True):
        new_item = st.text_input("Item Name")
        s_type = st.selectbox("Shop Category (e.g., Grocery, Vegetables)", ["Grocery", "Vegetables", "Stationary", "Hardware", "Medicine"])
        est_cost = st.number_input("Estimated Cost (₹)", min_value=0.0, step=10.0)
        
        if st.form_submit_button("Add to Pending List", use_container_width=True):
            if new_item:
                try:
                    today_str = get_ist_now().strftime("%d-%m-%Y")
                    # Date_Added, Item, Shop_Type, Est_Cost, Actual_Cost, Status, Date_Bought
                    row_data = [today_str, new_item, s_type, est_cost, "", "Pending", ""]
                    sh.worksheet("SHOPPING_LIST").append_row(row_data)
                    st.success(f"Added {new_item} to your {s_type} list!")
                except Exception as e:
                    st.error(f"Failed to save: {e}")

# ==========================================
# TAB 3: LOCATION ENTRY FORM
# ==========================================
with tab_location:
    st.markdown("### 🏫 Express School Route")
    
    express_container = st.container(border=True)
    with express_container:
        if not st.session_state.route_active:
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
                    row_data = [time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), express_move, "", express_people, "Started Express Route"]
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
            express_place = st.selectbox("Where did you arrive?", ["Karim Da's House (Keys)", "Bhagyabantapur Primary School", "Girishmore Bus Stop", "HOME"])
            
            forgot_keys_fwd = False
            forgot_keys_ret = False
            forgot_bus = False
            
            if express_place == "Bhagyabantapur Primary School":
                forgot_keys_fwd = st.checkbox("⚠️ I forgot to log Karim Da's House (Keys) on the way")
                if forgot_keys_fwd:
                    missed_time_fwd = st.time_input("Time you picked up the keys?", value=st.session_state.retro_time, step=60, key="fwd_keys")
            
            if express_place == "HOME":
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
                    
                    if forgot_keys_fwd and express_place == "Bhagyabantapur Primary School":
                        m_time_str = missed_time_fwd.strftime("%H:%M")
                        sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_str, "- Stationary -", "Karim Da's House (Keys)", arrival_people, "Retroactive arrival"])
                        sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_str, travel_mode, "", arrival_people, "Retroactive transit"])
                    
                    if express_place == "HOME":
                        if forgot_keys_ret:
                            m_time_k = missed_time_keys.strftime("%H:%M")
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_k, "- Stationary -", "Karim Da's House (Keys)", arrival_people, "Retroactive arrival"])
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_k, travel_mode, "", arrival_people, "Retroactive transit"])
                        if forgot_bus:
                            m_time_b = missed_time_bus.strftime("%H:%M")
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_b, "- Stationary -", "Girishmore Bus Stop", arrival_people, "Retroactive arrival"])
                            arrival_people = "I"
                            sh.worksheet("LOCATION_DATA").append_row([today_str, m_time_b, travel_mode, "", arrival_people, "Retroactive transit"])
                    
                    arr_row = [today_str, time_now.strftime("%H:%M"), "- Stationary -", express_place, arrival_people, ""]
                    sh.worksheet("LOCATION_DATA").append_row(arr_row)
                    
                    st.session_state.route_active = False
                    st.session_state.current_people = "I"
                    st.session_state.retro_time = get_ist_now().time()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.markdown("### 📝 Manual Location Log")
    location_logic = get_location_logic()

    loc_date = st.date_input("Log Date", value=st.session_state.locked_date)
    loc_time_str = st.text_input("Start Time (Type in 24hr format)", value=st.session_state.locked_time.strftime("%H:%M"))
    
    col1, col2 = st.columns(2)
    with col1:
        move_opts = ["- Stationary -"] + get_list("Moves")
        move = st.selectbox("Move Type", move_opts)
    with col2:
        area_options = ["- Select Area -", "- On the way -"] + list(location_logic.keys())
        area = st.selectbox("Select Route / Area", area_options)
    
    if area == "- On the way -":
        specific_place = ""
        st.info("🚲 Transit log.")
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
    
    if st.button("💾 Save Manual Entry", use_container_width=True):
        try:
            try:
                parsed_time = datetime.strptime(loc_time_str.strip(), "%H:%M")
                formatted_time = parsed_time.strftime("%H:%M")
            except ValueError:
                st.error("⚠️ Invalid time! Use HH:MM format.")
                st.stop()
                
            formatted_date = loc_date.strftime("%d.%m.%y")
            final_move = "" if move == "- Stationary -" else move
            
            row_data = [formatted_date, formatted_time, final_move, specific_place, people, loc_remark]
            sh.worksheet("LOCATION_DATA").append_row(row_data)
            
            st.success("Logged successfully!")
            st.session_state.locked_date = get_ist_now().date()
            st.session_state.locked_time = get_ist_now().time()
        except Exception as e:
            st.error(f"Error saving to Google Sheets: {e}")

# ==========================================
# TAB 4: ADVANCED ERP DASHBOARD
# ==========================================
with tab_dash:
    st.header("📊 Financial Intelligence")
    
    try:
        money_records = sh.worksheet("MONEY_DATA").get_all_records()
        df_money = pd.DataFrame(money_records)
        
        if not df_money.empty:
            df_money['In'] = pd.to_numeric(df_money['In'].replace('', 0), errors='coerce').fillna(0)
            df_money['Out'] = pd.to_numeric(df_money['Out'].replace('', 0), errors='coerce').fillna(0)
            
            # --- 1. THE FUND VISUALIZER (Plotly) ---
            st.subheader("💰 Virtual Fund Balances")
            if 'Fund' in df_money.columns:
                fund_summary = df_money.groupby('Fund').agg({'In': 'sum', 'Out': 'sum'}).reset_index()
                fund_summary['Current Balance'] = fund_summary['In'] - fund_summary['Out']
                
                # Plotly Bar Chart for stunning visuals
                fig_funds = px.bar(fund_summary, x='Fund', y='Current Balance', 
                                   title="Net Balance by Virtual Fund",
                                   color='Current Balance', color_continuous_scale="Viridis",
                                   text_auto='.2s')
                st.plotly_chart(fig_funds, use_container_width=True)
            else:
                st.warning("Start logging with the new 'Fund' dropdown to see charts here!")
            
            st.divider()

            # --- 2. THE REIMBURSEMENT ENGINE ---
            st.subheader("🔄 Cross-Fund Borrowing")
            st.write("Tracks money moving between School and Personal accounts.")
            
            # Logic: If you use a Personal Fund for a School Entity
            pers_paid_for_sch = df_money[(df_money['Fund'].isin(['Salary', 'Personal Savings'])) & (df_money['Entity'] == 'SCH')]['Out'].sum()
            sch_repaid_pers = df_money[(df_money['Fund'].isin(['Salary', 'Personal Savings'])) & (df_money['Entity'] == 'SCH')]['In'].sum()
            school_owes_you = pers_paid_for_sch - sch_repaid_pers
            
            # Logic: If you use School Fund for a Personal Entity
            sch_paid_for_pers = df_money[(df_money['Fund'].isin(['MDM', 'Sarba Sikha'])) & (df_money['Entity'] == 'PERS')]['Out'].sum()
            pers_repaid_sch = df_money[(df_money['Fund'].isin(['MDM', 'Sarba Sikha'])) & (df_money['Entity'] == 'PERS')]['In'].sum()
            you_owe_school = sch_paid_for_pers - pers_repaid_sch
            
            c1, c2 = st.columns(2)
            c1.metric("School Owes Salary/Personal", f"₹ {school_owes_you:,.2f}")
            c2.metric("Salary Owes MDM/School", f"₹ {you_owe_school:,.2f}")

            st.divider()

            # --- 3. EXPENSE BREAKDOWN ---
            st.subheader("🥧 Expense Breakdown by Entity")
            out_only = df_money[df_money['Out'] > 0]
            if not out_only.empty:
                fig_pie = px.pie(out_only, values='Out', names='Entity', title="Where is the money going?", hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
                
        else:
            st.info("No financial data available yet.")
    except Exception as e:
        st.error(f"Could not load Dashboard: {e}")

# ==========================================
# TAB 5: INSTRUCTIONS
# ==========================================
with tab_help:
    st.header("📖 ERP Manual")
    st.write("Your system now tracks Physical Accounts, Virtual Funds, and Location-Aware Shopping.")
