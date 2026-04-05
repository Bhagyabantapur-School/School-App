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

# Initialize Session States
if 'route_active' not in st.session_state: st.session_state.route_active = False
if 'route_type' not in st.session_state: st.session_state.route_type = None 
if 'active_route' not in st.session_state: st.session_state.active_route = ""
if 'current_people' not in st.session_state: st.session_state.current_people = "I"
if 'current_move' not in st.session_state: st.session_state.current_move = "BIKE"
if 'retro_time' not in st.session_state: st.session_state.retro_time = get_ist_now().time()
if 'locked_date' not in st.session_state: st.session_state.locked_date = get_ist_now().date()
if 'locked_time' not in st.session_state: st.session_state.locked_time = get_ist_now().time()

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

# --- SMART CACHING ENGINE ---
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
def load_shopping_data():
    try: return pd.DataFrame(sh.worksheet("SHOPPING_LIST").get_all_records())
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

def get_current_location():
    df_loc = load_location_data()
    if not df_loc.empty:
        last_record = df_loc.iloc[-1].to_dict()
        move_val = str(last_record.get('Move', '')).strip()
        if move_val in ["", "- Stationary -", "nan"]:
            return str(last_record.get('Place', ''))
    return None

def get_shop_type(place_name):
    if 'Specific_Place' in config_df.columns and 'Shop_Type' in config_df.columns:
        match = config_df[config_df['Specific_Place'].astype(str).str.strip() == place_name]
        if not match.empty:
            s_type = match['Shop_Type'].dropna().values
            if len(s_type) > 0 and str(s_type[0]).strip() != "":
                return str(s_type[0]).strip()
    return None

def sync_journey_state():
    if 'state_synced' not in st.session_state:
        df_loc = load_location_data()
        if not df_loc.empty:
            last_record = df_loc.iloc[-1].to_dict()
            move_val = str(last_record.get('Move', '')).strip()
            
            if move_val not in ["", "- Stationary -", "nan"]:
                st.session_state.route_active = True
                st.session_state.current_move = move_val
                st.session_state.current_people = str(last_record.get('People', 'I'))
                
                rem = str(last_record.get('Remark', ''))
                if "Started Route:" in rem:
                    st.session_state.active_route = rem.split("Started Route:")[-1].strip()
                    st.session_state.route_type = "Dynamic"
                else:
                    st.session_state.route_type = "Express" 
            else:
                st.session_state.route_active = False
                st.session_state.route_type = None
                
        st.session_state.state_synced = True

sync_journey_state()

# ==========================================
# APP LAYOUT & TABS
# ==========================================
st.title("📱 SK Ecosystem")

tab_money, tab_shopping, tab_location, tab_dash, tab_help = st.tabs(["💰 Money", "🛒 Shopping", "📍 Location", "📊 Dash", "📖 Help"])

current_loc = get_current_location()
current_shop_type = get_shop_type(current_loc) if current_loc else None

# ==========================================
# TAB 1: MONEY ENTRY FORM
# ==========================================
with tab_money:
    
    # --- 1. LOCATION HEADER & QUICK SYNC ---
    c_loc1, c_loc2 = st.columns([3, 1])
    with c_loc1:
        if current_loc and current_shop_type:
            st.success(f"📍 **{current_loc}** | 🛒 **{current_shop_type}**")
        elif current_loc:
            st.success(f"📍 Location: **{current_loc}**")
        else:
            st.info("📍 Location: Unknown")
    with c_loc2:
        if st.button("🔄 Sync Loc", use_container_width=True):
            load_location_data.clear()
            st.rerun()

    # --- 2. BUSY TIME QUICK ENTRY ---
    st.markdown("### ⚡ Busy Time Quick Entry")
    with st.container(border=True):
        bq_c1, bq_c2, bq_c3, bq_c4 = st.columns([1.5, 1.5, 1.2, 1.5])
        with bq_c1: b_type = st.radio("Flow Type", ["Expense (OUT)", "Income (IN)"], horizontal=True, label_visibility="collapsed")
        with bq_c2: b_amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, key="b_amt", label_visibility="collapsed")
        with bq_c3:
            chk_pers = st.checkbox("Entity: PERS", value=True)
            chk_mb = st.checkbox("Acc: MB", value=False)
        with bq_c4:
            if st.button("🚀 Fast Save", use_container_width=True, type="primary"):
                if b_amount > 0:
                    time_now = get_ist_now()
                    today_str = time_now.strftime("%d-%m-%Y")
                    time_str = time_now.strftime("%H:%M")
                    in_val = b_amount if "IN" in b_type else ""
                    out_val = b_amount if "OUT" in b_type else ""
                    
                    final_entity = "PERS" if chk_pers else ""
                    final_acc = "MB" if chk_mb else ""
                    
                    # 12 Columns now (Date, Time, In, Out, Account, Fund, Entity, Category, SubCat, Particulars, TO_FROM, Remark)
                    row_data = [today_str, time_str, in_val, out_val, final_acc, "", final_entity, "", "", "", current_loc or "", "⚠️ INCOMPLETE"]
                    sh.worksheet("MONEY_DATA").append_row(row_data)
                    load_money_data.clear()
                    st.success("Fast saved! Complete it later.")
                    st.rerun()
                else:
                    st.warning("Enter an amount!")
        
        st.caption(f"Location To/From: {current_loc or 'Unknown'}")

    st.divider()

    # --- 3. INCOMPLETE LIST MANAGER ---
    df_money = load_money_data()
    if not df_money.empty and 'Remark' in df_money.columns:
        incomplete_df = df_money[df_money['Remark'] == '⚠️ INCOMPLETE']
        if not incomplete_df.empty:
            st.error(f"⚠️ You have {len(incomplete_df)} incomplete Quick Entries waiting!")
            with st.expander("📂 Open Incomplete List to Complete"):
                for idx, row in incomplete_df.iterrows():
                    sheet_row = idx + 2
                    is_out = float(row.get('Out', 0) or 0) > 0
                    amt_display = f"₹{row['Out']} (OUT)" if is_out else f"₹{row['In']} (IN)"
                    
                    # Safely get time if it exists
                    row_time = row.get('Time', '')
                    time_disp = f" at {row_time}" if str(row_time).strip() != "" else ""
                    st.markdown(f"**Date:** {row['Date']}{time_disp} | **Amount:** {amt_display} | **Entity:** {row.get('Entity', '')} | **Acc:** {row.get('Account', '')} | **To/From:** {row['TO_FROM']}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1: 
                        # Default indices for the dropdowns if data exists
                        acc_opts = get_list("Accounts")
                        default_acc = acc_opts.index(row.get('Account', '')) if row.get('Account', '') in acc_opts else 0
                        i_acc = st.selectbox("Account", acc_opts, index=default_acc, key=f"ac_{idx}")
                        i_cat = st.selectbox("Category", get_list("Categories") + ["-None-"], key=f"ca_{idx}")
                    with c2: 
                        i_fund = st.selectbox("Fund", get_list("Funds"), key=f"fu_{idx}")
                        i_sub = st.selectbox("Sub Category", get_list("Sub-Categories") + ["-None-"], key=f"su_{idx}")
                    with c3:
                        i_part = st.selectbox("Particulars", get_list("Particulars") + ["-None-"], key=f"pa_{idx}")
                        i_rem = st.text_input("Remark", key=f"re_{idx}")
                    
                    if st.button("💾 Complete & Save Record", key=f"sv_{idx}", type="primary"):
                        try:
                            money_ws = sh.worksheet("MONEY_DATA")
                            final_cat = "" if i_cat == "-None-" else i_cat
                            final_sub = "" if i_sub == "-None-" else i_sub
                            final_part = "" if i_part == "-None-" else i_part
                            
                            row_data = [
                                row['Date'], row.get('Time', ''), row['In'], row['Out'], 
                                i_acc, i_fund, row.get('Entity', ''), 
                                final_cat, final_sub, final_part, 
                                row['TO_FROM'], i_rem
                            ]
                            # Updates A to L (12 columns)
                            cells = money_ws.range(f"A{sheet_row}:L{sheet_row}")
                            for i, val in enumerate(row_data): cells[i].value = str(val)
                            money_ws.update_cells(cells)
                            load_money_data.clear()
                            st.success("Record Completed!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    st.divider()

    # --- 4. EXPRESS SHOPPING CHECKOUT ---
    if current_loc and current_shop_type:
        df_shop = load_shopping_data()
        if not df_shop.empty and 'Status' in df_shop.columns:
            pending_items = df_shop[(df_shop['Status'] == 'Pending') & (df_shop['Shop_Type'] == current_shop_type)]
            if not pending_items.empty:
                st.markdown("### ⚡ Express 1-Click Checkout")
                shop_ws = sh.worksheet("SHOPPING_LIST") 
                for idx, row in pending_items.iterrows():
                    sheet_row = idx + 2 
                    with st.container(border=True):
                        colA, colB, colC = st.columns([2, 1, 1.5])
                        with colA:
                            st.write(f"**{row.get('Item', 'Unknown')}**")
                            st.caption(f"Fund: {row.get('Fund', '')} | Acc: {row.get('Account', '')}")
                        with colB:
                            final_cost = st.number_input("Cost", value=float(row.get('Est_Cost', 0) if pd.notna(row.get('Est_Cost')) else 0), key=f"cost_{idx}", label_visibility="collapsed")
                        with colC:
                            if st.button("💸 Pay & Clear", key=f"pay_{idx}", use_container_width=True, type="primary"):
                                try:
                                    part_name = str(row.get('Item', ''))
                                    match_row = config_df[config_df['Map_Particular'].astype(str).str.strip() == part_name]
                                    ent = str(match_row['Map_Entity'].values[0]) if not match_row.empty else "PERS"
                                    cat = str(match_row['Map_Category'].values[0]) if not match_row.empty else ""
                                    subcat = str(match_row['Map_SubCat'].values[0]) if not match_row.empty else ""
                                    rem = "Auto-cleared from list"
                                    
                                    time_now = get_ist_now()
                                    today_str = time_now.strftime("%d-%m-%Y")
                                    time_str = time_now.strftime("%H:%M")
                                    
                                    money_row = [today_str, time_str, "", final_cost, str(row.get('Account', '')), str(row.get('Fund', '')), ent, cat, subcat, part_name, current_loc, rem]
                                    sh.worksheet("MONEY_DATA").append_row(money_row)
                                    
                                    headers = shop_ws.row_values(1)
                                    shop_ws.update_cell(sheet_row, headers.index('Status') + 1, 'Bought')
                                    shop_ws.update_cell(sheet_row, headers.index('Actual_Cost') + 1, final_cost)
                                    shop_ws.update_cell(sheet_row, headers.index('Date_Bought') + 1, today_str)
                                    
                                    load_money_data.clear()
                                    load_shopping_data.clear()
                                    st.success(f"Cleared {part_name} from your list!")
                                    st.rerun()
                                except Exception as e: st.error(f"Error processing item: {e}")
                st.divider()

    # --- 5. STANDARD MANUAL FINANCIAL RECORD ---
    st.subheader("📝 Add Manual Financial Record")
    
    t_col1, t_col2 = st.columns(2)
    with t_col1: entry_date = st.date_input("Date", value=st.session_state.locked_date)
    with t_col2: entry_time_str = st.text_input("Time (HH:MM)", value=st.session_state.locked_time.strftime("%H:%M"))
    
    amt_col1, amt_col2 = st.columns(2)
    with amt_col1: amount_in = st.number_input("IN (Income/Receive)", min_value=0.0, step=10.0)
    with amt_col2: amount_out = st.number_input("OUT (Expense/Send)", min_value=0.0, step=10.0)
    
    col1, col2 = st.columns(2)
    with col1:
        account = st.selectbox("Account (Physical)", get_list("Accounts"))
        fund = st.selectbox("Fund (Virtual Source)", get_list("Funds"))
        
        mapped_entities = []
        if 'Map_Entity' in config_df.columns:
            mapped_entities = list(dict.fromkeys([str(e).strip() for e in config_df['Map_Entity'].dropna() if str(e).strip() != ""]))
        ent_opts = mapped_entities if mapped_entities else get_list("Entities")
        
        entity = st.selectbox("Entity", ent_opts)
        
        if 'Map_Entity' in config_df.columns:
            ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == entity]
            cat_opts = list(dict.fromkeys([str(c).strip() for c in ent_df['Map_Category'].dropna() if str(c).strip() != ""]))
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
        if not cat_df.empty and 'Map_SubCat' in cat_df.columns:
            sub_opts = list(dict.fromkeys([str(s).strip() for s in cat_df['Map_SubCat'].dropna() if str(s).strip() != ""]))
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
            part_opts = list(dict.fromkeys([str(p).strip() for p in sub_df['Map_Particular'].dropna() if str(p).strip() != ""]))
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
        if to_from == "-- Type New --": to_from = st.text_input("Type New TO / FROM")

    rem_opts = get_list("Remarks")
    remark_box = st.selectbox("Remark", ["- None -"] + rem_opts + ["-- Type New --"])
    if remark_box == "-- Type New --": remark = st.text_input("Type New Remark")
    elif remark_box == "- None -": remark = ""
    else: remark = remark_box
    
    if st.button("💾 Save Manual Money Entry", use_container_width=True):
        try:
            try:
                parsed_time = datetime.strptime(entry_time_str.strip(), "%H:%M")
                formatted_time = parsed_time.strftime("%H:%M")
            except ValueError:
                st.error("⚠️ Invalid time! Use HH:MM format.")
                st.stop()
                
            formatted_date = entry_date.strftime("%d-%m-%Y")
            row_data = [formatted_date, formatted_time, amount_in if amount_in > 0 else "", amount_out if amount_out > 0 else "", account, fund, entity, category, sub_cat, particulars, to_from, remark]
            sh.worksheet("MONEY_DATA").append_row(row_data)
            load_money_data.clear() 
            st.success(f"Saved: ₹{amount_in if amount_in > 0 else amount_out} logged to {to_from}!")
            st.session_state.locked_date = get_ist_now().date() 
        except Exception as e:
            st.error(f"Failed to save: {e}")

# ==========================================
# TAB 2: SHOPPING LIST (Planning Form)
# ==========================================
with tab_shopping:
    st.header("🛒 Smart Shopping List")
    st.subheader("➕ Plan Multiple Purchases")
    
    col1, col2 = st.columns(2)
    with col1:
        mapped_entities = []
        if 'Map_Entity' in config_df.columns:
            mapped_entities = list(dict.fromkeys([str(e).strip() for e in config_df['Map_Entity'].dropna() if str(e).strip() != ""]))
        p_ent_opts = mapped_entities if mapped_entities else get_list("Entities")
        
        p_entity = st.selectbox("Entity", p_ent_opts, key="plan_ent")
        
        if 'Map_Entity' in config_df.columns:
            p_ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == p_entity]
            p_cat_opts = list(dict.fromkeys([str(c).strip() for c in p_ent_df['Map_Category'].dropna() if str(c).strip() != ""]))
            p_category = st.selectbox("Category", p_cat_opts + ["-- Type New --"], key="plan_cat")
            if p_category == "-- Type New --":
                p_category = st.text_input("Type New Category", key="plan_cat_new")
                p_cat_df = pd.DataFrame() 
            else:
                p_cat_df = p_ent_df[p_ent_df['Map_Category'].astype(str).str.strip() == p_category]
        else:
            p_category = st.selectbox("Category", get_list("Categories") + ["-- Type New --"], key="plan_cat_fb")
            if p_category == "-- Type New --": p_category = st.text_input("Type New Category", key="plan_cat_new_fb")
            p_cat_df = pd.DataFrame()
            
        if not p_cat_df.empty and 'Map_SubCat' in p_cat_df.columns:
            p_sub_opts = list(dict.fromkeys([str(s).strip() for s in p_cat_df['Map_SubCat'].dropna() if str(s).strip() != ""]))
            p_sub_cat = st.selectbox("Sub Category", p_sub_opts + ["-- Type New --"], key="plan_sub")
            if p_sub_cat == "-- Type New --":
                p_sub_cat = st.text_input("Type New Sub Category", key="plan_sub_new")
                p_sub_df = pd.DataFrame()
            else:
                p_sub_df = p_cat_df[p_cat_df['Map_SubCat'].astype(str).str.strip() == p_sub_cat]
        else:
            p_sub_cat = st.selectbox("Sub Category", get_list("Sub-Categories") + ["-- Type New --"], key="plan_sub_fb")
            if p_sub_cat == "-- Type New --": p_sub_cat = st.text_input("Type New Sub Category", key="plan_sub_new_fb")
            p_sub_df = pd.DataFrame()
            
        if not p_sub_df.empty and 'Map_Particular' in p_sub_df.columns:
            p_part_opts = list(dict.fromkeys([str(p).strip() for p in p_sub_df['Map_Particular'].dropna() if str(p).strip() != ""]))
        else:
            p_part_opts = get_list("Particulars")
            
        selected_items = st.multiselect("Select Existing Items", p_part_opts, key="plan_item_multi")
        custom_items_str = st.text_input("Add New Items (Separate with commas, e.g. Apples, Milk)", key="plan_item_new_multi")
        
    with col2:
        shop_type_opts = []
        if 'Shop_Type' in config_df.columns:
            shop_type_opts = list(dict.fromkeys([str(s).strip() for s in config_df['Shop_Type'].dropna() if str(s).strip() != ""]))
        if not shop_type_opts: shop_type_opts = ["Grocery", "Vegetables", "Stationary", "Hardware", "Medicine"]
            
        s_type = st.selectbox("Shop Category", shop_type_opts + ["-- Type New --"], key="plan_stype")
        if s_type == "-- Type New --": s_type = st.text_input("Type New Shop Category", key="plan_stype_new")
            
        est_cost = st.number_input("Estimated Cost per item (₹)", min_value=0.0, step=10.0, key="plan_cost")
        fund = st.selectbox("Fund to use", get_list("Funds"), key="plan_fund")
        account = st.selectbox("Account to use", get_list("Accounts"), key="plan_acc")
        
    if st.button("➕ Add All to Pending List", use_container_width=True):
        all_items = selected_items + [i.strip() for i in custom_items_str.split(',') if i.strip()]
        if all_items:
            try:
                today_str = get_ist_now().strftime("%d-%m-%Y")
                rows_to_add = [[today_str, itm, s_type, est_cost, "", "Pending", "", fund, account] for itm in all_items]
                sh.worksheet("SHOPPING_LIST").append_rows(rows_to_add)
                load_shopping_data.clear() 
                st.success(f"Added {len(all_items)} items to your {s_type} list!")
            except Exception as e:
                st.error(f"Failed to save: {e}")
        else:
            st.warning("⚠️ Please select or type at least one item to add.")

    st.divider()
    st.subheader("📋 All Pending Items")
    df_shop = load_shopping_data()
    if not df_shop.empty and 'Status' in df_shop.columns:
        all_pending = df_shop[df_shop['Status'] == 'Pending']
        if not all_pending.empty:
            st.dataframe(all_pending[['Item', 'Shop_Type', 'Est_Cost', 'Fund']], use_container_width=True, hide_index=True)
        else: st.write("You have no pending items!")

# ==========================================
# TAB 3: LOCATION ENTRY FORM
# ==========================================
with tab_location:
    if not st.session_state.route_active or st.session_state.get('route_type') == "Dynamic":
        st.markdown("### 🗺️ Dynamic Area Route")
        dynamic_container = st.container(border=True)
        with dynamic_container:
            location_logic = get_location_logic()
            route_opts = list(location_logic.keys())
            
            if not st.session_state.route_active:
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    selected_route = st.selectbox("Select Route (Area)", route_opts, key="dyn_route")
                    dyn_move = st.selectbox("Travel Mode", ["BIKE", "WALK", "BIKE + WALK", "TOTO"], key="dyn_move")
                with d_col2:
                    people_opts = get_list("People")
                    if not people_opts: people_opts = ["I"]
                    if "I" not in people_opts: people_opts.insert(0, "I")
                    dyn_people = st.selectbox("Companions", people_opts, index=people_opts.index("I"), key="dyn_people")
                    
                if st.button("🟢 Start Journey", key="start_dyn", use_container_width=True):
                    try:
                        time_now = get_ist_now()
                        sh.worksheet("LOCATION_DATA").append_row([
                            time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), 
                            dyn_move, "", dyn_people, f"Started Route: {selected_route}"
                        ])
                        load_location_data.clear()
                        st.session_state.route_active = True
                        st.session_state.route_type = "Dynamic"
                        st.session_state.active_route = selected_route
                        st.session_state.current_move = dyn_move
                        st.session_state.current_people = dyn_people
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                    
            else:
                active_r = st.session_state.get('active_route', route_opts[0] if route_opts else "")
                active_m = st.session_state.get('current_move', 'Transit')
                active_p = st.session_state.get('current_people', 'I')
                
                st.success(f"🚲 Journey in progress... ({active_m} with {active_p} on {active_r})")
                
                places_for_route = location_logic.get(active_r, [])
                if not places_for_route: places_for_route = ["-- No places mapped --"]
                
                dyn_place = st.selectbox("Where did you arrive?", places_for_route, key="dyn_arrive")
                
                if st.button("🛑 Log Arrival", key="log_dyn", use_container_width=True, type="primary"):
                    try:
                        time_now = get_ist_now()
                        sh.worksheet("LOCATION_DATA").append_row([
                            time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), 
                            "- Stationary -", dyn_place, active_p, "Logged Arrival"
                        ])
                        load_location_data.clear()
                        st.session_state.route_active = False 
                        st.session_state.route_type = None
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    if not st.session_state.route_active or st.session_state.get('route_type') == "Express":
        st.markdown("### 🏫 Express School Route")
        express_container = st.container(border=True)
        with express_container:
            if not st.session_state.route_active:
                col1, col2 = st.columns(2)
                with col1: express_move = st.selectbox("Travel Mode", ["BIKE", "WALK", "BIKE + WALK", "TOTO"], key="exp_move")
                with col2:
                    people_opts = get_list("People")
                    if not people_opts: people_opts = ["I", "I, BKP, TKM", "I, TKM"]
                    if "I" not in people_opts: people_opts.insert(0, "I")
                    express_people = st.selectbox("Companions", people_opts, index=people_opts.index("I"), key="exp_people")
                    
                if st.button("🟢 Start Express Journey", use_container_width=True):
                    try:
                        time_now = get_ist_now()
                        sh.worksheet("LOCATION_DATA").append_row([time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), express_move, "", express_people, "Started Express Route"])
                        load_location_data.clear()
                        st.session_state.route_active = True
                        st.session_state.route_type = "Express"
                        st.session_state.current_people = express_people
                        st.session_state.current_move = express_move
                        st.session_state.retro_time = get_ist_now().time()
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
                        
                        sh.worksheet("LOCATION_DATA").append_row([today_str, time_now.strftime("%H:%M"), "- Stationary -", express_place, arrival_people, ""])
                        load_location_data.clear()
                        st.session_state.route_active = False
                        st.session_state.route_type = None
                        st.session_state.current_people = "I"
                        st.session_state.retro_time = get_ist_now().time()
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
    
    if st.button("🏠 Arrived HOME Now", use_container_width=True):
        try:
            time_now = get_ist_now()
            today_str = time_now.strftime("%d.%m.%y")
            time_str = time_now.strftime("%H:%M")
            sh.worksheet("LOCATION_DATA").append_row([today_str, time_str, "- Stationary -", "HOME", "I", "Quick Home Log"])
            st.session_state.route_active = False
            st.session_state.route_type = None
            st.session_state.current_people = "I"
            load_location_data.clear()
            st.success(f"Welcome Home! Logged at {time_str}")
            st.rerun()
        except Exception as e: st.error(f"Error logging Home: {e}")

    st.divider()

    st.markdown("### 📝 Manual Location Log")
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
        specific_place = st.selectbox("Specific Place", specific_place_options)
        if specific_place == "-- Type New --": specific_place = st.text_input("Type New Place Name")

    manual_people_opts = get_list("People")
    if not manual_people_opts: manual_people_opts = ["I"]
    if "I" not in manual_people_opts: manual_people_opts.insert(0, "I")
    people = st.selectbox("People", manual_people_opts, index=manual_people_opts.index("I"))
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
            sh.worksheet("LOCATION_DATA").append_row([formatted_date, formatted_time, final_move, specific_place, people, loc_remark])
            load_location_data.clear()
            st.success("Logged successfully!")
            st.session_state.locked_date = get_ist_now().date()
            st.session_state.locked_time = get_ist_now().time()
        except Exception as e: st.error(f"Error saving to Google Sheets: {e}")

# ==========================================
# TAB 4: ADVANCED ERP DASHBOARD
# ==========================================
with tab_dash:
    st.header("📊 Financial Intelligence")
    df_money = load_money_data()
    if not df_money.empty:
        df_money_clean = df_money[df_money['Remark'] != '⚠️ INCOMPLETE'].copy()
        
        if not df_money_clean.empty:
            df_money_clean['In'] = pd.to_numeric(df_money_clean['In'].replace('', 0), errors='coerce').fillna(0)
            df_money_clean['Out'] = pd.to_numeric(df_money_clean['Out'].replace('', 0), errors='coerce').fillna(0)
            
            st.subheader("💰 Virtual Fund Balances")
            if 'Fund' in df_money_clean.columns:
                fund_summary = df_money_clean.groupby('Fund').agg({'In': 'sum', 'Out': 'sum'}).reset_index()
                fund_summary = fund_summary[fund_summary['Fund'] != ""] 
                fund_summary['Current Balance'] = fund_summary['In'] - fund_summary['Out']
                fig_funds = px.bar(fund_summary, x='Fund', y='Current Balance', title="Net Balance by Virtual Fund", color='Current Balance', color_continuous_scale="Viridis", text_auto='.2s')
                st.plotly_chart(fig_funds, use_container_width=True)
            
            st.divider()

            st.subheader("🔄 Cross-Fund Borrowing")
            if 'Fund' in df_money_clean.columns:
                pers_paid_for_sch = df_money_clean[(df_money_clean['Fund'].isin(['Salary', 'Personal Savings'])) & (df_money_clean['Entity'] == 'SCH')]['Out'].sum()
                sch_repaid_pers = df_money_clean[(df_money_clean['Fund'].isin(['Salary', 'Personal Savings'])) & (df_money_clean['Entity'] == 'SCH')]['In'].sum()
                school_owes_you = pers_paid_for_sch - sch_repaid_pers
                
                sch_paid_for_pers = df_money_clean[(df_money_clean['Fund'].isin(['MDM', 'Sarba Sikha'])) & (df_money_clean['Entity'] == 'PERS')]['Out'].sum()
                pers_repaid_sch = df_money_clean[(df_money_clean['Fund'].isin(['MDM', 'Sarba Sikha'])) & (df_money_clean['Entity'] == 'PERS')]['In'].sum()
                you_owe_school = sch_paid_for_pers - pers_repaid_sch
                
                c1, c2 = st.columns(2)
                c1.metric("School Owes Salary/Personal", f"₹ {school_owes_you:,.2f}")
                c2.metric("Salary Owes MDM/School", f"₹ {you_owe_school:,.2f}")

            st.divider()

            st.subheader("🥧 Expense Breakdown by Entity")
            out_only = df_money_clean[df_money_clean['Out'] > 0]
            if not out_only.empty:
                fig_pie = px.pie(out_only, values='Out', names='Entity', title="Where is the money going?", hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Complete your incomplete records to view charts!")
            
        st.divider()
        
        st.subheader("⏱️ Today's Location Log")
        df_loc = load_location_data()
        if not df_loc.empty:
            latest_date = df_loc['Date'].iloc[-1]
            df_today = df_loc[df_loc['Date'] == latest_date].copy()
            df_today['Time_Obj'] = pd.to_datetime(df_today['Time'], format='%H:%M', errors='coerce')
            time_diffs = df_today['Time_Obj'].shift(-1) - df_today['Time_Obj']
            def format_duration(td):
                if pd.isnull(td): return "Current"
                total_seconds = int(td.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                return f"{hours}:{minutes:02d}"
            df_today['Duration'] = time_diffs.apply(format_duration)
            display_cols = ['Time', 'Duration', 'Move', 'Place', 'People', 'Remark']
            st.dataframe(df_today[display_cols], use_container_width=True, hide_index=True)
        else: st.info("No location logs found yet.")
    else: st.info("No financial data available yet.")

# ==========================================
# TAB 5: INSTRUCTIONS
# ==========================================
with tab_help:
    st.header("📖 ERP Manual")
    st.write("You MUST manually insert a 'Time' column into your MONEY_DATA Google Sheet right after the 'Date' column for the new 12-column system to function.")
