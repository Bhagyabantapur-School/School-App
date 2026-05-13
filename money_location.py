import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import pandas as pd
from datetime import datetime, timedelta, timezone, date
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="SK Ecosystem - Core", page_icon="📱", layout="centered")

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

@st.cache_data(ttl=60)
def load_bike_data():
    try: return pd.DataFrame(sh.worksheet("BIKE_LOG").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

# --- SMART ACCOUNT PARSER ---
ACCOUNT_HEADERS = [
    "A. Cash:", "B. Bank Accounts:", "C. Credit Cards:", 
    "D. Digital Wallet:", "E. Loan:", "F. Members:"
]

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
                p1 = str(places[i]).strip()
                p2 = str(places[i+1]).strip()
                mode = str(modes[i]).strip().upper()
                fare = str(fares[i]).strip()
                
                if p1 and p2:
                    rule_mode = mode if mode and mode not in ['NAN', 'NONE'] else None
                    try: rule_fare = float(fare) if fare.lower() not in ['nan', '', 'none'] else 0.0
                    except: rule_fare = 0.0
                    
                    if rule_mode or rule_fare > 0:
                        key = frozenset([p1, p2])
                        rules[key] = {'mode': rule_mode, 'fare': rule_fare}
    return rules

def get_current_location_details():
    df_loc = load_location_data()
    if not df_loc.empty:
        last_record = df_loc.iloc[-1].to_dict()
        move_val = str(last_record.get('Move', '')).strip()
        if move_val in ["", "- Stationary -", "nan"]:
            loc = str(last_record.get('Place', '')).strip()
            date_str = str(last_record.get('Date', ''))
            time_str = str(last_record.get('Time', ''))
            duration_str = ""
            try:
                loc_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%y %H:%M")
                now = get_ist_now().replace(tzinfo=None)
                diff = now - loc_dt
                total_seconds = int(diff.total_seconds())
                
                if total_seconds >= 0:
                    days, remainder = divmod(total_seconds, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, _ = divmod(remainder, 60)
                    if days > 0:
                        duration_str = f"{days}d {hours}h"
                    elif hours > 0:
                        duration_str = f"{hours}h {minutes}m"
                    else:
                        duration_str = f"{minutes}m"
            except Exception:
                pass
            return loc, duration_str
    return None, None

def get_shop_type(place_name):
    if 'Specific_Place' in config_df.columns and 'Shop_Type' in config_df.columns:
        match = config_df[config_df['Specific_Place'].astype(str).str.strip() == place_name]
        if not match.empty:
            s_type = match['Shop_Type'].dropna().values
            if len(s_type) > 0 and str(s_type[0]).strip() != "":
                return str(s_type[0]).strip()
    return None

def should_inject_tofrom(loc_name):
    if not loc_name:
        return False
    loc_lower = str(loc_name).strip().lower()
    if loc_lower == "home" or "house" in loc_lower:
        return False
    return True

# ==========================================
# AUTO MIDNIGHT ROLLOVER ENGINE
# ==========================================
def check_midnight_rollover():
    df_loc = load_location_data()
    if not df_loc.empty:
        last_record = df_loc.iloc[-1].to_dict()
        last_date_str = str(last_record.get('Date', ''))
        try:
            last_dt = datetime.strptime(last_date_str, "%d.%m.%y").date()
            time_now = get_ist_now()
            today_dt = time_now.date()
            
            if last_dt < today_dt:
                last_move = str(last_record.get('Move', ''))
                last_place = str(last_record.get('Place', ''))
                last_people = str(last_record.get('People', 'I'))
                
                days_diff = (today_dt - last_dt).days
                rows_to_add = []
                
                for i in range(1, days_diff + 1):
                    missing_date = last_dt + timedelta(days=i)
                    missing_date_str = missing_date.strftime("%d.%m.%y")
                    rows_to_add.append([
                        missing_date_str, "00:00", last_move, last_place, last_people, "Auto Midnight Rollover"
                    ])
                
                if rows_to_add:
                    sh.worksheet("LOCATION_DATA").append_rows(rows_to_add)
                    load_location_data.clear()
                    return True 
        except Exception as e:
            pass 
    return False

if check_midnight_rollover():
    st.rerun()

# ==========================================
# DYNAMIC HOME ROSTER ENGINE
# ==========================================
def get_home_occupants(arriving_people_str):
    time_now = get_ist_now()
    
    if time_now.hour >= 14:
        return "I Baso, Suborno, Mother"
        
    df_loc = load_location_data()
    
    safe_arriving_str = arriving_people_str.replace('I Baso', 'I, Baso')
    arriving_people = set([p.strip() for p in safe_arriving_str.split(',') if p.strip()])
    
    order = ["I", "Baso", "Suborno", "Mother"]
    
    if df_loc.empty:
        now_home = arriving_people.union({"Baso", "Suborno", "Mother"})
        ordered_home = [p for p in order if p in now_home] + [p for p in now_home if p not in order]
        return ", ".join(ordered_home).replace("I, Baso", "I Baso")

    last_home_idx = -1
    for i in range(len(df_loc)-1, -1, -1):
        if str(df_loc.iloc[i].get('Place', '')).strip() == 'HOME' and str(df_loc.iloc[i].get('Move', '')).strip() == '- Stationary -':
            last_home_idx = i
            break

    if last_home_idx != -1:
        past_home_str = str(df_loc.iloc[last_home_idx].get('People', ''))
        safe_past_str = past_home_str.replace('I Baso', 'I, Baso')
        past_home_people = set([p.strip() for p in safe_past_str.split(',') if p.strip()])

        if last_home_idx < len(df_loc) - 1:
            depart_str = str(df_loc.iloc[last_home_idx + 1].get('People', ''))
            safe_depart_str = depart_str.replace('I Baso', 'I, Baso')
            depart_people = set([p.strip() for p in safe_depart_str.split(',') if p.strip()])
            
            stayed_home = past_home_people - depart_people
            now_home = stayed_home.union(arriving_people)
        else:
            now_home = past_home_people.union(arriving_people)
    else:
        now_home = arriving_people.union({"Baso", "Suborno", "Mother"})
        
    ordered_home = [p for p in order if p in now_home] + [p for p in now_home if p not in order]
    
    return ", ".join(ordered_home).replace("I, Baso", "I Baso")

def sync_journey_state():
    if 'state_synced' not in st.session_state:
        df_loc = load_location_data()
        if not df_loc.empty:
            recent_route = None
            if 'Remark' in df_loc.columns:
                for remark in reversed(df_loc['Remark'].tolist()):
                    rem_str = str(remark)
                    if "Started Route:" in rem_str:
                        route_part = rem_str.split("Started Route:")[-1].split("towards")[0].strip()
                        recent_route = route_part
                        break
            st.session_state.last_used_route = recent_route

            last_record = df_loc.iloc[-1].to_dict()
            move_val = str(last_record.get('Move', '')).strip()
            
            st.session_state.current_people = str(last_record.get('People', 'I'))
            
            if move_val not in ["", "- Stationary -", "nan"]:
                st.session_state.route_active = True
                st.session_state.current_move = move_val
                
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
# APP LAYOUT & TABS
# ==========================================
st.title("📱 SK Ecosystem - Core")

# --- ONLY MONEY AND LOCATION TABS REMAIN ---
tab_money, tab_location = st.tabs(["💰 Money", "📍 Location"])

current_loc, loc_duration = get_current_location_details()
current_shop_type = get_shop_type(current_loc) if current_loc else None

# ==========================================
# TAB 1: MONEY ENTRY FORM
# ==========================================
with tab_money:
    c_loc1, c_loc2 = st.columns([3, 1])
    with c_loc1:
        loc_display = f"📍 Location: **{current_loc}** ({loc_duration})" if loc_duration else f"📍 Location: **{current_loc}**"
        if current_loc and current_shop_type:
            st.success(f"{loc_display} | 🛒 **{current_shop_type}**")
        elif current_loc:
            st.success(loc_display)
        else:
            st.info("📍 Location: Unknown")
    with c_loc2:
        if st.button("🔄 Sync Loc", use_container_width=True):
            load_location_data.clear()
            st.rerun()

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
                    
                    final_tf = current_loc if should_inject_tofrom(current_loc) else ""
                    
                    row_data = [today_str, time_str, in_val, out_val, final_acc, "", final_entity, "", "", "", final_tf, current_loc or "", "⚠️ INCOMPLETE"]
                    sh.worksheet("MONEY_DATA").append_row(row_data)
                    load_money_data.clear()
                    st.success("Fast saved! Complete it later.")
                    st.rerun()
                else:
                    st.warning("Enter an amount!")
        
        st.caption(f"Logged under App Location: {current_loc or 'Unknown'}")

    # --- BIKE REFUEL EXPANDER ---
    with st.expander("🏍️ Quick Log: Bike Refuel & Auto-Mileage"):
        df_bike = load_bike_data()
        last_odo = 0
        if not df_bike.empty and 'Odometer' in df_bike.columns:
            last_odo = int(df_bike.iloc[-1]['Odometer'])
            
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1: b_odo = st.number_input("Current Odometer", min_value=last_odo, value=last_odo, step=1)
        with b_col2: b_litres = st.number_input("Petrol (Litres)", min_value=0.0, step=0.1)
        with b_col3: b_cost = st.number_input("Total Cost (₹)", min_value=0.0, step=10.0)
        
        b_acc_col1, b_acc_col2 = st.columns(2)
        with b_acc_col1: b_acc = st.selectbox("Paid From", get_clean_accounts(), key="bike_pay_acc")
        with b_acc_col2: 
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⛽ Save Refuel Log", use_container_width=True, type="primary"):
                if b_odo > last_odo and b_litres > 0 and b_cost > 0:
                    try:
                        time_now = get_ist_now()
                        date_str = time_now.strftime("%d-%m-%Y")
                        time_str = time_now.strftime("%H:%M")
                        
                        # 1. Log to BIKE_LOG
                        sh.worksheet("BIKE_LOG").append_row([date_str, time_str, b_odo, b_litres, b_cost])
                        
                        # 2. Automatically log to MONEY_DATA
                        tf_val = current_loc if should_inject_tofrom(current_loc) else "Petrol Pump"
                        sh.worksheet("MONEY_DATA").append_row([
                            date_str, time_str, "", b_cost, b_acc, "Salary", "PERS", "NEEDS", 
                            "Transport", "Petrol", tf_val, current_loc or "", f"Odo: {b_odo}"
                        ])
                        
                        load_bike_data.clear()
                        load_money_data.clear()
                        st.success("⛽ Refuel Logged! Mileage updated in Dashboard.")
                        st.rerun()
                    except Exception as e:
                        if "WorksheetNotFound" in str(e):
                            st.error("⚠️ Error: Please create a sheet tab named 'BIKE_LOG' first!")
                        else:
                            st.error(f"Error: {e}")
                else:
                    st.warning("⚠️ Ensure Odometer is higher than last time, and Litres/Cost are greater than 0.")

    st.divider()

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
                    
                    row_time = row.get('Time', '')
                    time_disp = f" at {row_time}" if str(row_time).strip() != "" else ""
                    
                    st.markdown(f"**Date:** {row['Date']}{time_disp} | **Amount:** {amt_display} | **Loc:** {row.get('Location', '')}")
                    
                    c_r1_1, c_r1_2, c_r1_3 = st.columns(3)
                    with c_r1_1: 
                        acc_opts = get_clean_accounts()
                        default_acc = acc_opts.index(row.get('Account', '')) if row.get('Account', '') in acc_opts else 0
                        i_acc = st.selectbox("Account", acc_opts, index=default_acc, key=f"ac_{idx}")
                    with c_r1_2: 
                        i_fund = st.selectbox("Fund", get_list("Funds"), key=f"fu_{idx}")
                    with c_r1_3:
                        mapped_entities = []
                        if 'Map_Entity' in config_df.columns:
                            mapped_entities = list(dict.fromkeys([str(e).strip() for e in config_df['Map_Entity'].dropna() if str(e).strip() != ""]))
                        ent_opts = mapped_entities if mapped_entities else get_list("Entities")
                        
                        curr_ent = str(row.get('Entity', '')).strip()
                        if curr_ent and curr_ent not in ent_opts:
                            ent_opts.insert(0, curr_ent)
                        default_ent_idx = ent_opts.index(curr_ent) if curr_ent in ent_opts else 0
                        i_ent = st.selectbox("Entity", ent_opts, index=default_ent_idx, key=f"en_{idx}")

                    c_r2_1, c_r2_2, c_r2_3 = st.columns(3)
                    with c_r2_1:
                        if 'Map_Entity' in config_df.columns:
                            ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == i_ent]
                            cat_opts = list(dict.fromkeys([str(c).strip() for c in ent_df['Map_Category'].dropna() if str(c).strip() != ""]))
                            i_cat = st.selectbox("Category", cat_opts + ["-- Type New --", "-None-"], key=f"ca_{idx}")
                            if i_cat == "-- Type New --":
                                i_cat = st.text_input("Type New Category", key=f"ca_new_{idx}")
                                cat_df = pd.DataFrame() 
                            else:
                                cat_df = ent_df[ent_df['Map_Category'].astype(str).str.strip() == i_cat]
                        else:
                            i_cat = st.selectbox("Category", get_list("Categories") + ["-- Type New --", "-None-"], key=f"ca_{idx}")
                            if i_cat == "-- Type New --": i_cat = st.text_input("Type New Category", key=f"ca_new_{idx}")
                            cat_df = pd.DataFrame()
                            
                    with c_r2_2:
                        if not cat_df.empty and 'Map_SubCat' in cat_df.columns:
                            sub_opts = list(dict.fromkeys([str(s).strip() for s in cat_df['Map_SubCat'].dropna() if str(s).strip() != ""]))
                            i_sub = st.selectbox("Sub Category", sub_opts + ["-- Type New --", "-None-"], key=f"su_{idx}")
                            if i_sub == "-- Type New --":
                                i_sub = st.text_input("Type New Sub Category", key=f"su_new_{idx}")
                                sub_df = pd.DataFrame()
                            else:
                                sub_df = cat_df[cat_df['Map_SubCat'].astype(str).str.strip() == i_sub]
                        else:
                            i_sub = st.selectbox("Sub Category", get_list("Sub-Categories") + ["-- Type New --", "-None-"], key=f"su_{idx}")
                            if i_sub == "-- Type New --": i_sub = st.text_input("Type New Sub Category", key=f"su_new_{idx}")
                            sub_df = pd.DataFrame()
                            
                    with c_r2_3:
                        if not sub_df.empty and 'Map_Particular' in sub_df.columns:
                            part_opts = list(dict.fromkeys([str(p).strip() for p in sub_df['Map_Particular'].dropna() if str(p).strip() != ""]))
                            i_part = st.selectbox("Particulars", part_opts + ["-- Type New --", "-None-"], key=f"pa_{idx}")
                            if i_part == "-- Type New --":
                                i_part = st.text_input("Type New Particulars", key=f"pa_new_{idx}")
                        else:
                            i_part = st.selectbox("Particulars", get_list("Particulars") + ["-- Type New --", "-None-"], key=f"pa_{idx}")
                            if i_part == "-- Type New --": i_part = st.text_input("Type New Particulars", key=f"pa_new_{idx}")

                    c_r3_1, c_r3_2, c_r3_3 = st.columns([1.5, 1.5, 1])
                    with c_r3_1:
                        tf_opts = get_list("TO_FROM")
                        curr_tf = str(row.get('TO_FROM', '')).strip()
                        if curr_tf and curr_tf not in tf_opts:
                            tf_opts.insert(0, curr_tf)
                            
                        tf_opts_with_none = tf_opts + ["-None-"]
                        default_tf = tf_opts_with_none.index(curr_tf) if curr_tf in tf_opts_with_none else (len(tf_opts_with_none)-1)
                        i_tofrom = st.selectbox("TO / FROM", tf_opts_with_none, index=default_tf, key=f"tf_{idx}")
                    
                    with c_r3_2:
                        i_rem = st.text_input("Remark", key=f"re_{idx}")
                        
                    with c_r3_3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("💾 Save", key=f"sv_{idx}", type="primary", use_container_width=True):
                            try:
                                money_ws = sh.worksheet("MONEY_DATA")
                                final_cat = "" if i_cat == "-None-" else i_cat
                                final_sub = "" if i_sub == "-None-" else i_sub
                                final_part = "" if i_part == "-None-" else i_part
                                final_tf = "" if i_tofrom == "-None-" else i_tofrom
                                
                                row_data = [
                                    row['Date'], row.get('Time', ''), row['In'], row['Out'], 
                                    i_acc, i_fund, i_ent, 
                                    final_cat, final_sub, final_part, 
                                    final_tf, row.get('Location', ''), i_rem
                                ]
                                cells = money_ws.range(f"A{sheet_row}:M{sheet_row}")
                                for i, val in enumerate(row_data): cells[i].value = str(val)
                                money_ws.update_cells(cells)
                                load_money_data.clear()
                                st.success("Record Completed!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    st.divider()

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
                            raw_cost = row.get('Est_Cost', 0)
                            try: safe_cost = float(raw_cost) if str(raw_cost).strip() != "" else 0.0
                            except (ValueError, TypeError): safe_cost = 0.0
                            
                            final_cost = st.number_input("Cost", value=safe_cost, key=f"cost_{idx}", label_visibility="collapsed")
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
                                    
                                    final_tf = current_loc if should_inject_tofrom(current_loc) else ""
                                    
                                    money_row = [today_str, time_str, "", final_cost, str(row.get('Account', '')), str(row.get('Fund', '')), ent, cat, subcat, part_name, final_tf, current_loc, rem]
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

    st.subheader("📝 Add Manual Financial Record")
    
    t_col1, t_col2 = st.columns(2)
    with t_col1: entry_date = st.date_input("Date", value=st.session_state.locked_date)
    with t_col2: entry_time_str = st.text_input("Time (HH:MM)", value=st.session_state.locked_time.strftime("%H:%M"))
    
    amt_col1, amt_col2 = st.columns(2)
    with amt_col1: amount_in = st.number_input("IN (Income/Receive)", min_value=0.0, step=10.0)
    with amt_col2: amount_out = st.number_input("OUT (Expense/Send)", min_value=0.0, step=10.0)
    
    col1, col2 = st.columns(2)
    with col1:
        account = st.selectbox("Account (Physical)", get_clean_accounts())
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
        to_from_opts = ["-- Type New --", "- None -"] + mapped_tofrom
        default_index = 1
        
        if should_inject_tofrom(current_loc):
            if current_loc not in to_from_opts:
                to_from_opts.insert(2, current_loc)
                default_index = 2
            else:
                default_index = to_from_opts.index(current_loc)
        
        to_from = st.selectbox("TO / FROM (Person/Entity)", to_from_opts, index=default_index)
        if to_from == "-- Type New --": to_from = st.text_input("Type New TO / FROM")
        elif to_from == "- None -": to_from = ""

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
            row_data = [formatted_date, formatted_time, amount_in if amount_in > 0 else "", amount_out if amount_out > 0 else "", account, fund, entity, category, sub_cat, particulars, to_from, current_loc or "", remark]
            sh.worksheet("MONEY_DATA").append_row(row_data)
            load_money_data.clear() 
            st.success(f"Saved: ₹{amount_in if amount_in > 0 else amount_out} logged!")
            st.session_state.locked_date = get_ist_now().date() 
        except Exception as e:
            st.error(f"Failed to save: {e}")

# ==========================================
# TAB 2: LOCATION ENTRY FORM
# ==========================================
with tab_location:
    
    if 'target_destination' not in st.session_state: 
        st.session_state.target_destination = ""

    if not st.session_state.route_active or st.session_state.get('route_type') == "Dynamic":
        st.markdown("### 🗺️ Dynamic Area Route")
        dynamic_container = st.container(border=True)
        with dynamic_container:
            location_logic = get_location_logic()
            route_opts = list(location_logic.keys())
            
            if not st.session_state.route_active:
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    default_idx = 0
                    if st.session_state.get('last_used_route') in route_opts:
                        default_idx = route_opts.index(st.session_state.last_used_route)
                        
                    selected_route = st.selectbox("Select Route (Area)", route_opts, index=default_idx, key="dyn_route")
                    
                    places_for_route = location_logic.get(selected_route, [])
                    if not places_for_route: places_for_route = ["-- No places mapped --"]
                    
                    is_sequential = selected_route.strip().lower().endswith('route')
                    
                    if is_sequential:
                        dir_col1, dir_col2 = st.columns([1, 1])
                        with dir_col1:
                            route_direction = st.radio("Direction", ["Forward", "Return"], horizontal=True, key="dyn_dir")
                            
                        if current_loc in places_for_route:
                            current_idx = places_for_route.index(current_loc)
                            if route_direction == "Forward":
                                available_places = places_for_route[current_idx + 1:]
                            else:
                                available_places = places_for_route[:current_idx][::-1]
                            
                            if not available_places:
                                available_places = places_for_route 
                        else:
                            available_places = places_for_route if route_direction == "Forward" else places_for_route[::-1]
                    else:
                        available_places = places_for_route

                    out_of_route = st.checkbox("📍 Visit place outside this route")
                    
                    if out_of_route:
                        all_places = get_list("Places")
                        dyn_next_stop_sel = st.selectbox("Next Stop (Other Place)", all_places + ["-- Type New --"], key="dyn_other_place")
                        if dyn_next_stop_sel == "-- Type New --":
                            dyn_next_stop = st.text_input("Type New Place Name", key="dyn_new_place")
                        else:
                            dyn_next_stop = dyn_next_stop_sel
                    else:
                        dyn_next_stop = st.selectbox("Next Stop", available_places, key="dyn_next_stop")
                    
                    # FETCH SMART TRANSIT RULES
                    transit_rules = get_transit_rules()
                    current_pair = frozenset([str(current_loc).strip(), str(dyn_next_stop).strip()]) if current_loc else None
                    
                    # If it's a complex (doesn't end with "route"), default to WALK
                    pre_mode = "WALK" if not is_sequential else "BIKE"
                    base_fare = 0.0
                    
                    if current_pair in transit_rules:
                        if transit_rules[current_pair]['mode']:
                            pre_mode = transit_rules[current_pair]['mode']
                        base_fare = transit_rules[current_pair]['fare']

                    move_options = ["BIKE", "WALK", "BIKE + WALK", "TOTO", "AUTO", "BUS"]
                    if pre_mode and pre_mode not in move_options: move_options.append(pre_mode)
                    default_mode_idx = move_options.index(pre_mode) if pre_mode in move_options else 0
                    
                    dyn_move = st.selectbox("Travel Mode", move_options, index=default_mode_idx, key="dyn_move")
                    
                    # ZERO FARE MAGIC
                    if dyn_move in ["WALK", "BIKE", "BIKE + WALK"]:
                        base_fare = 0.0
                    
                with d_col2:
                    people_opts = get_list("People")
                    if not people_opts: people_opts = ["I"]
                    if "I" not in people_opts: people_opts.insert(0, "I")
                    
                    # REMEMBER COMPANIONS
                    default_people_idx = people_opts.index(st.session_state.current_people) if st.session_state.current_people in people_opts else 0
                    dyn_people = st.selectbox("Companions", people_opts, index=default_people_idx, key="dyn_people")
                    
                    # AUTO COMPANION TICKETS CALCULATION
                    total_people = len([p for p in dyn_people.replace('I Baso', 'I, Baso').split(',') if p.strip()]) if dyn_people != "I" else 1
                    
                    child_tix = st.number_input("Child/Half Fares (Included in Companions)", min_value=0, max_value=total_people, value=0, step=1, key="dyn_child")
                    
                    actual_adults = total_people - child_tix
                    calc_fare = (actual_adults * base_fare) + (child_tix * (base_fare / 2))
                    
                    if base_fare > 0:
                        st.info(f"🧮 **Auto-Fare:** {actual_adults} Adult + {child_tix} Child/Half = **₹{calc_fare}**")
                        
                    fare_amt = st.number_input("Total Fare Amount (₹)", min_value=0.0, step=5.0, value=float(calc_fare))
                    
                    acc_opts = get_clean_accounts()
                    default_acc_idx = acc_opts.index("MB") if "MB" in acc_opts else 0
                    fare_acc = st.selectbox("Pay From", acc_opts, index=default_acc_idx, key="dyn_fare_acc")
                
                st.markdown("<br>", unsafe_allow_html=True)
                c_btn1, c_btn2 = st.columns(2)
                
                with c_btn1:
                    if st.button("🟢 Start Journey (New Area/Road)", key="start_dyn", use_container_width=True, type="primary"):
                        if not dyn_next_stop or str(dyn_next_stop).strip() == "":
                            st.error("⚠️ Please specify the next stop!")
                        else:
                            try:
                                time_now = get_ist_now()
                                loc_date_str = time_now.strftime("%d.%m.%y")
                                money_date_str = time_now.strftime("%d-%m-%Y")
                                time_str = time_now.strftime("%H:%M")
                                
                                # Road Transit -> Place is empty
                                sh.worksheet("LOCATION_DATA").append_row([
                                    loc_date_str, time_str, 
                                    dyn_move, "", dyn_people, f"Started Route: {selected_route} towards {dyn_next_stop}"
                                ])
                                
                                if fare_amt > 0:
                                    start_point = current_loc if current_loc else "Unknown"
                                    part_str = f"{dyn_move} ({start_point} - {dyn_next_stop})"
                                    remark_str = f"with {dyn_people}" if dyn_people != "I" else ""
                                    
                                    money_row = [
                                        money_date_str, time_str, "", fare_amt, 
                                        fare_acc, "Salary", "PERS", "VISIT", selected_route, 
                                        part_str, start_point, start_point, remark_str
                                    ]
                                    sh.worksheet("MONEY_DATA").append_row(money_row)
                                    load_money_data.clear()
                                
                                load_location_data.clear()
                                st.session_state.route_active = True
                                st.session_state.route_type = "Dynamic"
                                st.session_state.active_route = selected_route
                                st.session_state.last_used_route = selected_route
                                st.session_state.current_move = dyn_move
                                st.session_state.current_people = dyn_people
                                st.session_state.target_destination = dyn_next_stop
                                st.success(f"Started journey to {dyn_next_stop}!" + (f" Paid ₹{fare_amt} fare." if fare_amt > 0 else ""))
                                st.rerun()
                            except Exception as e: st.error(f"Error: {e}")

                with c_btn2:
                    if st.button("🚶‍♂️ Move Inside Same Complex", key="internal_dyn", use_container_width=True):
                        if not dyn_next_stop or str(dyn_next_stop).strip() == "":
                            st.error("⚠️ Please specify the next stop!")
                        else:
                            try:
                                time_now = get_ist_now()
                                loc_date_str = time_now.strftime("%d.%m.%y")
                                money_date_str = time_now.strftime("%d-%m-%Y")
                                time_str = time_now.strftime("%H:%M")
                                
                                # Internal Move -> Place stays as the current complex (selected_route)
                                sh.worksheet("LOCATION_DATA").append_row([
                                    loc_date_str, time_str, 
                                    dyn_move, selected_route, dyn_people, f"Started Route: {selected_route} towards {dyn_next_stop}"
                                ])
                                
                                if fare_amt > 0:
                                    start_point = current_loc if current_loc else "Unknown"
                                    part_str = f"{dyn_move} ({start_point} - {dyn_next_stop})"
                                    remark_str = f"with {dyn_people}" if dyn_people != "I" else ""
                                    
                                    money_row = [
                                        money_date_str, time_str, "", fare_amt, 
                                        fare_acc, "Salary", "PERS", "VISIT", selected_route, 
                                        part_str, start_point, start_point, remark_str
                                    ]
                                    sh.worksheet("MONEY_DATA").append_row(money_row)
                                    load_money_data.clear()
                                
                                load_location_data.clear()
                                st.session_state.route_active = True
                                st.session_state.route_type = "Dynamic"
                                st.session_state.active_route = selected_route
                                st.session_state.last_used_route = selected_route
                                st.session_state.current_move = dyn_move
                                st.session_state.current_people = dyn_people
                                st.session_state.target_destination = dyn_next_stop
                                st.success(f"Moving inside {selected_route} towards {dyn_next_stop}!" + (f" Paid ₹{fare_amt}." if fare_amt > 0 else ""))
                                st.rerun()
                            except Exception as e: st.error(f"Error: {e}")
                    
            else:
                active_r = st.session_state.get('active_route', route_opts[0] if route_opts else "")
                active_m = st.session_state.get('current_move', 'Transit')
                active_p = st.session_state.get('current_people', 'I')
                target_dest = st.session_state.get('target_destination', 'Destination')
                
                st.success(f"🚲 Journey in progress... ({active_m} with {active_p} towards {target_dest})")
                
                out_of_route_arr = st.checkbox("📍 Diverted to a different place?")
                if out_of_route_arr:
                    all_places = get_list("Places")
                    dyn_place_sel = st.selectbox("Actual Arrival Place", all_places + ["-- Type New --"])
                    if dyn_place_sel == "-- Type New --":
                        dyn_place = st.text_input("Type New Place Name")
                    else:
                        dyn_place = dyn_place_sel
                else:
                    places_for_route = location_logic.get(active_r, [])
                    if target_dest not in places_for_route: places_for_route.insert(0, target_dest)
                    dyn_place = st.selectbox("Confirm Arrival Place", places_for_route, index=places_for_route.index(target_dest), key="dyn_arrive")
                
                if st.button(f"🛑 Log Arrival at chosen place", key="log_dyn", use_container_width=True, type="primary"):
                    if not dyn_place or str(dyn_place).strip() == "":
                        st.error("⚠️ Please specify your arrival place!")
                    else:
                        try:
                            time_now = get_ist_now()
                            
                            arr_remark = "Logged Arrival"
                            final_arr_people = active_p
                            
                            # SMART OVERRIDES
                            if dyn_place == "Girishmore Bus Stop" and "Suborno" in active_p:
                                arr_remark = "Waiting for School Bus"
                            elif dyn_place == "HOME":
                                final_arr_people = get_home_occupants(active_p)
                                
                            sh.worksheet("LOCATION_DATA").append_row([
                                time_now.strftime("%d.%m.%y"), time_now.strftime("%H:%M"), 
                                "- Stationary -", dyn_place, final_arr_people, arr_remark
                            ])
                            load_location_data.clear()
                            st.session_state.route_active = False 
                            st.session_state.route_type = None
                            st.session_state.target_destination = ""
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
                    
                    # REMEMBER COMPANIONS
                    default_people_idx = people_opts.index(st.session_state.current_people) if st.session_state.current_people in people_opts else 0
                    express_people = st.selectbox("Companions", people_opts, index=default_people_idx, key="exp_people")
                    
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
                        
                        # --- SMART ARRIVAL OVERRIDES ---
                        arr_remark_exp = ""
                        final_arr_people = arrival_people
                        
                        if express_place == "Girishmore Bus Stop" and "Suborno" in arrival_people:
                            arr_remark_exp = "Waiting for School Bus"
                        elif express_place == "HOME":
                            final_arr_people = get_home_occupants(arrival_people)
                            
                        sh.worksheet("LOCATION_DATA").append_row([today_str, time_now.strftime("%H:%M"), "- Stationary -", express_place, final_arr_people, arr_remark_exp])
                        load_location_data.clear()
                        st.session_state.route_active = False
                        st.session_state.route_type = None
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
    
    # --- CONTEXT AWARE BUTTON: SUBORNO BOARDED BUS ---
    if current_loc == "Girishmore Bus Stop" and "Suborno" in st.session_state.current_people and not st.session_state.route_active:
        if st.button("🚌 Suborno Boarded Bus", use_container_width=True, type="primary"):
            try:
                time_now = get_ist_now()
                today_str = time_now.strftime("%d.%m.%y")
                time_str = time_now.strftime("%H:%M")
                sh.worksheet("LOCATION_DATA").append_row([
                    today_str, time_str, "- Stationary -", "Girishmore Bus Stop", "I", "Suborno boarded bus to school"
                ])
                st.session_state.current_people = "I"
                load_location_data.clear()
                st.success(f"Logged Suborno boarding bus at {time_str}. You are now traveling alone.")
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")
    
    if st.button("🏠 Arrived HOME Now", use_container_width=True):
        try:
            time_now = get_ist_now()
            today_str = time_now.strftime("%d.%m.%y")
            time_str = time_now.strftime("%H:%M")
            
            final_arr_people = get_home_occupants(st.session_state.current_people)
            
            sh.worksheet("LOCATION_DATA").append_row([today_str, time_str, "- Stationary -", "HOME", final_arr_people, "Quick Home Log"])
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
    
    default_manual_people = manual_people_opts.index(st.session_state.current_people) if st.session_state.current_people in manual_people_opts else 0
    people = st.selectbox("People", manual_people_opts, index=default_manual_people)
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
