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
st.set_page_config(page_title="SK Money Manager", page_icon="💰", layout="centered")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

# Initialize Session States
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

@st.cache_data(ttl=60)
def load_bike_data():
    try: return pd.DataFrame(sh.worksheet("BIKE_LOG").get_all_records())
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

def get_shop_type(place_name):
    if not place_name: return None
    place_col = next((c for c in config_df.columns if str(c).strip().replace('_', ' ').lower() in ['specific place', 'place']), None)
    type_col = next((c for c in config_df.columns if str(c).strip().replace('_', ' ').lower() in ['shop type', 'shop category']), None)
    
    if place_col and type_col:
        safe_place = str(place_name).strip().lower()
        match = config_df[config_df[place_col].astype(str).str.strip().str.lower() == safe_place]
        if not match.empty:
            s_type = match[type_col].dropna().values
            if len(s_type) > 0 and str(s_type[0]).strip() != "":
                return str(s_type[0]).strip()
    return None

def should_inject_tofrom(loc_name):
    if not loc_name: return False
    loc_lower = str(loc_name).strip().lower()
    if loc_lower == "home" or "house" in loc_lower: return False
    return True

# ==========================================
# APP LAYOUT
# ==========================================
st.title("💰 SK Money Manager")

current_loc, loc_duration = get_current_location_details()
current_shop_type = get_shop_type(current_loc) if current_loc else None

c_loc1, c_loc2 = st.columns([3, 1])
with c_loc1:
    loc_display = f"📍 Location: **{current_loc}** ({loc_duration})" if loc_duration else f"📍 Location: **{current_loc}**"
    if current_loc and current_shop_type: st.success(f"{loc_display} | 🛒 **{current_shop_type}**")
    elif current_loc: 
        st.success(loc_display)
        st.caption(f"*(No Shop Type mapped for '{current_loc}' in CONFIG)*")
    else: st.info("📍 Location: Unknown")
        
with c_loc2:
    if st.button("🔄 Sync", use_container_width=True):
        load_location_data.clear()
        load_config.clear()
        load_shopping_data.clear()
        st.rerun()

# --- EXPANDABLE BUSY TIME QUICK ENTRY ---
with st.expander("⚡ Busy Time Quick Entry", expanded=True):
    b_type = st.radio("Flow Type", ["Expense (OUT)", "Income (IN)"], horizontal=True)
    
    c_amt1, c_amt2, c_amt3 = st.columns([1, 1, 1])
    with c_amt1: b_amount = st.number_input("Total Amount (₹)", min_value=0.0, step=10.0, key="b_amt")
    with c_amt2: b_due = st.number_input("Due / Pay Later (₹)", min_value=0.0, max_value=float(b_amount), value=0.0, step=1.0, key="b_due")
    with c_amt3:
        st.markdown("<br>", unsafe_allow_html=True)
        chk_pers = st.checkbox("Entity: PERS", value=True)
        chk_mb = st.checkbox("Paid Acc: MB", value=False)

    if st.button("🚀 Fast Save", use_container_width=True, type="primary"):
        if b_amount > 0:
            time_now = get_ist_now()
            today_str, time_str = time_now.strftime("%d-%m-%Y"), time_now.strftime("%H:%M")
            
            final_entity = "PERS" if chk_pers else ""
            final_tf = current_loc if should_inject_tofrom(current_loc) else ""
            
            b_paid = b_amount - b_due
            
            if b_paid > 0:
                sh.worksheet("MONEY_DATA").append_row([today_str, time_str, b_paid if "IN" in b_type else "", b_paid if "OUT" in b_type else "", "MB" if chk_mb else "", "", final_entity, "", "", "", final_tf, current_loc or "", "⚠️ INCOMPLETE"])
            if b_due > 0:
                sh.worksheet("MONEY_DATA").append_row([today_str, time_str, b_due if "IN" in b_type else "", b_due if "OUT" in b_type else "", "UNPAID", "", final_entity, "", "", "", final_tf, current_loc or "", "⚠️ INCOMPLETE"])
                
            load_money_data.clear()
            st.success(f"Fast saved! Paid: ₹{b_paid}, Due: ₹{b_due}.")
            st.rerun()
        else: st.warning("Enter an amount!")
    
    st.caption(f"Logged under App Location: {current_loc or 'Unknown'}")
    
    st.divider()
    df_money_temp = load_money_data()
    if not df_money_temp.empty and 'Remark' in df_money_temp.columns:
        incomp_temp = df_money_temp[df_money_temp['Remark'] == '⚠️ INCOMPLETE']
        if not incomp_temp.empty:
            st.markdown("**📋 Last 5 Incomplete Entries:**")
            for _, row in incomp_temp.tail(5).iterrows():
                amt_display = f"₹{row['Out']} (OUT)" if float(row.get('Out', 0) or 0) > 0 else f"₹{row['In']} (IN)"
                if str(row.get('Account', '')).strip() == 'UNPAID': st.caption(f"🔴 **{row.get('Date', '')}** at {row.get('Time', '')} | **{amt_display}** | Loc: {row.get('Location', '')} | **(DUE)**")
                else: st.caption(f"🔸 **{row.get('Date', '')}** at {row.get('Time', '')} | **{amt_display}** | Loc: {row.get('Location', '')}")
        else: st.caption("✅ No incomplete quick entries waiting!")

# --- BIKE REFUEL EXPANDER ---
with st.expander("🏍️ Quick Log: Bike Refuel & Auto-Mileage"):
    df_bike = load_bike_data()
    last_odo = int(df_bike.iloc[-1]['Odometer']) if not df_bike.empty and 'Odometer' in df_bike.columns else 0
        
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
                    date_str, time_str = time_now.strftime("%d-%m-%Y"), time_now.strftime("%H:%M")
                    
                    sh.worksheet("BIKE_LOG").append_row([date_str, time_str, b_odo, b_litres, b_cost])
                    sh.worksheet("MONEY_DATA").append_row([date_str, time_str, "", b_cost, b_acc, "Salary", "PERS", "NEEDS", "Transport", "Petrol", current_loc if should_inject_tofrom(current_loc) else "Petrol Pump", current_loc or "", f"Odo: {b_odo}"])
                    load_bike_data.clear()
                    load_money_data.clear()
                    st.success("⛽ Refuel Logged! Mileage updated in Dashboard.")
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
            else: st.warning("⚠️ Ensure Odometer is higher than last time, and Litres/Cost are greater than 0.")

st.divider()

df_money = load_money_data()
if not df_money.empty and 'Remark' in df_money.columns:
    incomplete_df = df_money[df_money['Remark'] == '⚠️ INCOMPLETE']
    if not incomplete_df.empty:
        st.error(f"⚠️ You have {len(incomplete_df)} incomplete Quick Entries waiting!")
        with st.expander("📂 Open Incomplete List to Complete"):
            for idx, row in incomplete_df.iterrows():
                sheet_row = idx + 2
                amt_display = f"₹{row['Out']} (OUT)" if float(row.get('Out', 0) or 0) > 0 else f"₹{row['In']} (IN)"
                st.markdown(f"**Date:** {row['Date']}{' at ' + row.get('Time', '') if str(row.get('Time', '')).strip() else ''} | **Amount:** {amt_display} | **Loc:** {row.get('Location', '')}")
                
                c_r1_1, c_r1_2, c_r1_3 = st.columns(3)
                with c_r1_1: 
                    acc_opts = get_clean_accounts()
                    row_acc = str(row.get('Account', '')).strip()
                    if row_acc and row_acc not in acc_opts: acc_opts.insert(0, row_acc)
                    i_acc = st.selectbox("Account", acc_opts, index=acc_opts.index(row_acc) if row_acc in acc_opts else 0, key=f"ac_{idx}")
                with c_r1_2: i_fund = st.selectbox("Fund", get_list("Funds"), key=f"fu_{idx}")
                with c_r1_3:
                    mapped_entities = list(dict.fromkeys([str(e).strip() for e in config_df['Map_Entity'].dropna() if str(e).strip() != ""])) if 'Map_Entity' in config_df.columns else []
                    ent_opts = mapped_entities if mapped_entities else get_list("Entities")
                    curr_ent = str(row.get('Entity', '')).strip()
                    if curr_ent and curr_ent not in ent_opts: ent_opts.insert(0, curr_ent)
                    i_ent = st.selectbox("Entity", ent_opts, index=ent_opts.index(curr_ent) if curr_ent in ent_opts else 0, key=f"en_{idx}")

                c_r2_1, c_r2_2, c_r2_3 = st.columns(3)
                with c_r2_1:
                    if 'Map_Entity' in config_df.columns:
                        ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == i_ent]
                        cat_opts = list(dict.fromkeys([str(c).strip() for c in ent_df['Map_Category'].dropna() if str(c).strip() != ""]))
                        i_cat_sel = st.selectbox("Category", cat_opts + ["-- Type New --", "-None-"], key=f"ca_{idx}")
                        i_cat = st.text_input("Type New Category", key=f"ca_new_{idx}") if i_cat_sel == "-- Type New --" else i_cat_sel
                        cat_df = pd.DataFrame() if i_cat_sel == "-- Type New --" else ent_df[ent_df['Map_Category'].astype(str).str.strip() == i_cat]
                    else:
                        i_cat_sel = st.selectbox("Category", get_list("Categories") + ["-- Type New --", "-None-"], key=f"ca_{idx}")
                        i_cat = st.text_input("Type New Category", key=f"ca_new_{idx}") if i_cat_sel == "-- Type New --" else i_cat_sel
                        cat_df = pd.DataFrame()
                        
                with c_r2_2:
                    if not cat_df.empty and 'Map_SubCat' in cat_df.columns:
                        sub_opts = list(dict.fromkeys([str(s).strip() for s in cat_df['Map_SubCat'].dropna() if str(s).strip() != ""]))
                        i_sub_sel = st.selectbox("Sub Category", sub_opts + ["-- Type New --", "-None-"], key=f"su_{idx}")
                        i_sub = st.text_input("Type New Sub Category", key=f"su_new_{idx}") if i_sub_sel == "-- Type New --" else i_sub_sel
                        sub_df = pd.DataFrame() if i_sub_sel == "-- Type New --" else cat_df[cat_df['Map_SubCat'].astype(str).str.strip() == i_sub]
                    else:
                        i_sub_sel = st.selectbox("Sub Category", get_list("Sub-Categories") + ["-- Type New --", "-None-"], key=f"su_{idx}")
                        i_sub = st.text_input("Type New Sub Category", key=f"su_new_{idx}") if i_sub_sel == "-- Type New --" else i_sub_sel
                        sub_df = pd.DataFrame()
                        
                with c_r2_3:
                    if not sub_df.empty and 'Map_Particular' in sub_df.columns:
                        part_opts = list(dict.fromkeys([str(p).strip() for p in sub_df['Map_Particular'].dropna() if str(p).strip() != ""]))
                        i_part_sel = st.selectbox("Particulars", part_opts + ["-- Type New --", "-None-"], key=f"pa_{idx}")
                        i_part = st.text_input("Type New Particulars", key=f"pa_new_{idx}") if i_part_sel == "-- Type New --" else i_part_sel
                    else:
                        i_part_sel = st.selectbox("Particulars", get_list("Particulars") + ["-- Type New --", "-None-"], key=f"pa_{idx}")
                        i_part = st.text_input("Type New Particulars", key=f"pa_new_{idx}") if i_part_sel == "-- Type New --" else i_part_sel

                c_r3_1, c_r3_2, c_r3_3 = st.columns([1.5, 1.5, 1])
                with c_r3_1:
                    tf_opts = get_list("TO_FROM")
                    curr_tf = str(row.get('TO_FROM', '')).strip()
                    if curr_tf and curr_tf not in tf_opts: tf_opts.insert(0, curr_tf)
                    tf_opts_with_none = tf_opts + ["-None-"]
                    i_tofrom = st.selectbox("TO / FROM", tf_opts_with_none, index=tf_opts_with_none.index(curr_tf) if curr_tf in tf_opts_with_none else (len(tf_opts_with_none)-1), key=f"tf_{idx}")
                
                with c_r3_2: i_rem = st.text_input("Remark", key=f"re_{idx}")
                    
                with c_r3_3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾 Save", key=f"sv_{idx}", type="primary", use_container_width=True):
                        try:
                            cells = sh.worksheet("MONEY_DATA").range(f"A{sheet_row}:M{sheet_row}")
                            row_data = [row['Date'], row.get('Time', ''), row['In'], row['Out'], i_acc, i_fund, i_ent, "" if i_cat == "-None-" else i_cat, "" if i_sub == "-None-" else i_sub, "" if i_part == "-None-" else i_part, "" if i_tofrom == "-None-" else i_tofrom, row.get('Location', ''), i_rem]
                            for i, val in enumerate(row_data): cells[i].value = str(val)
                            sh.worksheet("MONEY_DATA").update_cells(cells)
                            load_money_data.clear()
                            st.success("Record Completed!")
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                st.divider()

# --- BULLETPROOF EXPRESS CHECKOUT FOR PENDING SHOPPING ---
if current_loc and current_shop_type:
    df_shop = load_shopping_data()
    status_col = next((c for c in df_shop.columns if str(c).strip().lower() == 'status'), None)
    stype_col = next((c for c in df_shop.columns if str(c).strip().replace('_', ' ').lower() in ['shop type', 'shop_type', 'shop category']), None)
    item_col = next((c for c in df_shop.columns if str(c).strip().lower() == 'item'), 'Item')
    fund_col = next((c for c in df_shop.columns if str(c).strip().lower() == 'fund'), 'Fund')
    acc_col = next((c for c in df_shop.columns if str(c).strip().lower() == 'account'), 'Account')
    cost_col = next((c for c in df_shop.columns if str(c).strip().replace('_', ' ').lower() in ['est cost', 'estimated cost', 'est_cost']), 'Est_Cost')
    
    if status_col and stype_col:
        pending_items = df_shop[(df_shop[status_col].astype(str).str.strip().str.lower() == 'pending') & (df_shop[stype_col].astype(str).str.strip().str.lower() == str(current_shop_type).strip().lower())]
        
        if not pending_items.empty:
            st.markdown(f"### ⚡ Express 1-Click Checkout ({current_shop_type})")
            shop_ws = sh.worksheet("SHOPPING_LIST") 
            headers = shop_ws.row_values(1)
            s_idx = next((i for i, h in enumerate(headers) if str(h).strip().lower() == 'status'), None)
            c_idx = next((i for i, h in enumerate(headers) if str(h).strip().replace('_', ' ').lower() in ['actual cost', 'actual_cost']), None)
            d_idx = next((i for i, h in enumerate(headers) if str(h).strip().replace('_', ' ').lower() in ['date bought', 'date_bought']), None)

            for idx, row in pending_items.iterrows():
                sheet_row = idx + 2 
                with st.container(border=True):
                    colA, colB, colC = st.columns([2, 1, 1.5])
                    with colA:
                        st.write(f"**{row.get(item_col, 'Unknown')}**")
                        st.caption(f"Fund: {row.get(fund_col, '')} | Acc: {row.get(acc_col, '')}")
                    with colB:
                        raw_cost = row.get(cost_col, 0)
                        try: safe_cost = float(raw_cost) if str(raw_cost).strip() != "" else 0.0
                        except (ValueError, TypeError): safe_cost = 0.0
                        final_cost = st.number_input("Cost", value=safe_cost, key=f"cost_{idx}", label_visibility="collapsed")
                    with colC:
                        if st.button("💸 Pay & Clear", key=f"pay_{idx}", use_container_width=True, type="primary"):
                            try:
                                part_name = str(row.get(item_col, ''))
                                ent, cat, subcat = "PERS", "", ""
                                map_part_col = next((c for c in config_df.columns if str(c).strip().replace('_', ' ').lower() == 'map particular'), None)
                                if map_part_col:
                                    match_row = config_df[config_df[map_part_col].astype(str).str.strip().str.lower() == part_name.strip().lower()]
                                    if not match_row.empty:
                                        if 'Map_Entity' in config_df.columns: ent = str(match_row['Map_Entity'].values[0])
                                        if 'Map_Category' in config_df.columns: cat = str(match_row['Map_Category'].values[0])
                                        if 'Map_SubCat' in config_df.columns: subcat = str(match_row['Map_SubCat'].values[0])
                                        
                                time_now = get_ist_now()
                                today_str, time_str = time_now.strftime("%d-%m-%Y"), time_now.strftime("%H:%M")
                                
                                sh.worksheet("MONEY_DATA").append_row([today_str, time_str, "", final_cost, str(row.get(acc_col, '')), str(row.get(fund_col, '')), ent, cat, subcat, part_name, current_loc if should_inject_tofrom(current_loc) else "", current_loc, "Auto-cleared from list"])
                                
                                if s_idx is not None: shop_ws.update_cell(sheet_row, s_idx + 1, 'Bought')
                                if c_idx is not None: shop_ws.update_cell(sheet_row, c_idx + 1, final_cost)
                                if d_idx is not None: shop_ws.update_cell(sheet_row, d_idx + 1, today_str)
                                
                                load_money_data.clear()
                                load_shopping_data.clear()
                                st.success(f"Cleared {part_name} from your list!")
                                st.rerun()
                            except Exception as e: st.error(f"Error processing item: {e}")
            st.divider()

# --- EXPANDABLE MANUAL FINANCIAL RECORD ---
with st.expander("📝 Add Manual Financial Record", expanded=False):
    t_col1, t_col2 = st.columns(2)
    with t_col1: entry_date = st.date_input("Date", value=st.session_state.locked_date)
    with t_col2: entry_time_str = st.text_input("Time (HH:MM)", value=st.session_state.locked_time.strftime("%H:%M"))
    
    amt_col1, amt_col2 = st.columns(2)
    with amt_col1: amount_in = st.number_input("IN (Income/Receive)", min_value=0.0, step=10.0)
    with amt_col2: amount_out = st.number_input("OUT (Expense/Send)", min_value=0.0, step=10.0)
    
    col1, col2 = st.columns(2)
    with col1:
        acc_opts = get_clean_accounts()
        if 'UNPAID' not in acc_opts: acc_opts.insert(0, 'UNPAID')
        account = st.selectbox("Account (Physical)", acc_opts)
        fund = st.selectbox("Fund (Virtual Source)", get_list("Funds"))
        
        mapped_entities = list(dict.fromkeys([str(e).strip() for e in config_df['Map_Entity'].dropna() if str(e).strip() != ""])) if 'Map_Entity' in config_df.columns else []
        entity = st.selectbox("Entity", mapped_entities if mapped_entities else get_list("Entities"))
        
        if 'Map_Entity' in config_df.columns:
            ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == entity]
            cat_opts = list(dict.fromkeys([str(c).strip() for c in ent_df['Map_Category'].dropna() if str(c).strip() != ""]))
            category_sel = st.selectbox("Category", cat_opts + ["-- Type New --"])
            category = st.text_input("Type New Category") if category_sel == "-- Type New --" else category_sel
            cat_df = pd.DataFrame() if category_sel == "-- Type New --" else ent_df[ent_df['Map_Category'].astype(str).str.strip() == category]
        else:
            category_sel = st.selectbox("Category", get_list("Categories") + ["-- Type New --"])
            category = st.text_input("Type New Category") if category_sel == "-- Type New --" else category_sel
            cat_df = pd.DataFrame()
            
    with col2:
        if not cat_df.empty and 'Map_SubCat' in cat_df.columns:
            sub_opts = list(dict.fromkeys([str(s).strip() for s in cat_df['Map_SubCat'].dropna() if str(s).strip() != ""]))
            sub_cat_sel = st.selectbox("Sub Category", sub_opts + ["-- Type New --"])
            sub_cat = st.text_input("Type New Sub Category") if sub_cat_sel == "-- Type New --" else sub_cat_sel
            sub_df = pd.DataFrame() if sub_cat_sel == "-- Type New --" else cat_df[cat_df['Map_SubCat'].astype(str).str.strip() == sub_cat]
        else:
            sub_cat_sel = st.selectbox("Sub Category", get_list("Sub-Categories") + ["-- Type New --"])
            sub_cat = st.text_input("Type New Sub Category") if sub_cat_sel == "-- Type New --" else sub_cat_sel
            sub_df = pd.DataFrame()
        
        if not sub_df.empty and 'Map_Particular' in sub_df.columns:
            part_opts = list(dict.fromkeys([str(p).strip() for p in sub_df['Map_Particular'].dropna() if str(p).strip() != ""]))
            particulars_sel = st.selectbox("Particulars", part_opts + ["-- Type New --"])
            particulars = st.text_input("Type New Particulars") if particulars_sel == "-- Type New --" else particulars_sel
        else:
            particulars_sel = st.selectbox("Particulars", get_list("Particulars") + ["-- Type New --"])
            particulars = st.text_input("Type New Particulars") if particulars_sel == "-- Type New --" else particulars_sel
            
        mapped_tofrom = get_list("TO_FROM")
        to_from_opts = ["-- Type New --", "- None -"] + mapped_tofrom
        default_index = 1
        if should_inject_tofrom(current_loc):
            if current_loc not in to_from_opts:
                to_from_opts.insert(2, current_loc)
                default_index = 2
            else: default_index = to_from_opts.index(current_loc)
        
        to_from_sel = st.selectbox("TO / FROM (Person/Entity)", to_from_opts, index=default_index)
        to_from = st.text_input("Type New TO / FROM") if to_from_sel == "-- Type New --" else ("" if to_from_sel == "- None -" else to_from_sel)

    rem_opts = get_list("Remarks")
    remark_box_sel = st.selectbox("Remark", ["- None -"] + rem_opts + ["-- Type New --"])
    remark = st.text_input("Type New Remark") if remark_box_sel == "-- Type New --" else ("" if remark_box_sel == "- None -" else remark_box_sel)
    
    if st.button("💾 Save Manual Money Entry", use_container_width=True):
        try:
            try: parsed_time = datetime.strptime(entry_time_str.strip(), "%H:%M").strftime("%H:%M")
            except ValueError: st.error("⚠️ Invalid time! Use HH:MM format."); st.stop()
                
            sh.worksheet("MONEY_DATA").append_row([entry_date.strftime("%d-%m-%Y"), parsed_time, amount_in if amount_in > 0 else "", amount_out if amount_out > 0 else "", account, fund, entity, category, sub_cat, particulars, to_from, current_loc or "", remark])
            load_money_data.clear() 
            st.success(f"Saved: ₹{amount_in if amount_in > 0 else amount_out} logged!")
            st.session_state.update(locked_date=get_ist_now().date(), locked_time=get_ist_now().time())
        except Exception as e: st.error(f"Failed to save: {e}")
