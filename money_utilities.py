import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone, date
import calendar
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="SK Dashboard Extras", page_icon="📊", layout="centered")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

# Initialize Session States needed for these tabs
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
def load_bills_data():
    try: return pd.DataFrame(sh.worksheet("PAYMENT_CHECKLIST").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_cash_data():
    try: return pd.DataFrame(sh.worksheet("CASH_COUNT").get_all_records())
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

def get_cash_wallets():
    raw = get_list("Accounts")
    wallets = []
    in_cash = False
    for a in raw:
        if a == "A. Cash:":
            in_cash = True
            continue
        elif a in ACCOUNT_HEADERS:
            in_cash = False
            
        if in_cash and a.strip():
            wallets.append(a.strip())
    return wallets

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
# APP LAYOUT & TABS
# ==========================================
st.title("📊 SK Dashboard Extras")

tab_cash, tab_shopping, tab_bills, tab_dash, tab_help = st.tabs(["💵 Cash", "🛒 Shopping", "✅ Bills", "📊 Dash", "📖 Help"])

# Required for Location-Aware Bill & Shopping Checkout Logic
current_loc, loc_duration = get_current_location_details()
current_shop_type = get_shop_type(current_loc) if current_loc else None

# ==========================================
# TAB 1: PHYSICAL CASH COUNT
# ==========================================
with tab_cash:
    st.header("💵 Physical Cash Denomination Count")
    st.write("Tally your physical cash balance on hand.")

    df_cash = load_cash_data()
    
    if not df_cash.empty:
        df_cash.columns = [str(c).strip() for c in df_cash.columns]

    st.subheader("Wallet Selection")
    
    # DYNAMIC CASH WALLET LIST
    cash_wallets = get_cash_wallets()
    
    existing_wallets = []
    if not df_cash.empty and 'Wallet_Name' in df_cash.columns:
        existing_wallets = list(df_cash['Wallet_Name'].dropna().unique())
        existing_wallets = [str(w).strip() for w in existing_wallets if str(w).strip() != ""]
    
    combined_wallets = list(dict.fromkeys(cash_wallets + existing_wallets))
    if not combined_wallets: 
        combined_wallets = ["Main Wallet", "Home Locker"]
        
    wallet_choice = st.selectbox("Select Wallet / Storage", combined_wallets + ["-- Add New Wallet --"])
    if wallet_choice == "-- Add New Wallet --":
        wallet_name = st.text_input("Type New Wallet Name")
    else:
        wallet_name = wallet_choice

    last_notes = {
        '500': 0, '200': 0, '100': 0, '50': 0, '20': 0, 
        '10_Note': 0, '10_Coin': 0, '5': 0, '2': 0, '1': 0
    }
    last_wallet_amt = 0.0

    if not df_cash.empty and wallet_name and wallet_name in existing_wallets:
        wallet_history = df_cash[df_cash['Wallet_Name'].astype(str).str.strip() == wallet_name]
        if not wallet_history.empty:
            last_entry = wallet_history.iloc[-1] 
            
            def get_prev_val(col_name, is_float=False):
                try:
                    if col_name in df_cash.columns:
                        val = last_entry[col_name]
                        return float(val) if is_float else int(val)
                except (ValueError, TypeError):
                    pass
                return 0.0 if is_float else 0

            last_notes['500'] = get_prev_val('₹500')
            last_notes['200'] = get_prev_val('₹200')
            last_notes['100'] = get_prev_val('₹100')
            last_notes['50']  = get_prev_val('₹50')
            last_notes['20']  = get_prev_val('₹20')
            last_notes['10_Note'] = get_prev_val('₹10_Note')
            last_notes['10_Coin'] = get_prev_val('₹10_Coin')
            last_notes['5']   = get_prev_val('₹5')
            last_notes['2']   = get_prev_val('₹2')
            last_notes['1']   = get_prev_val('₹1')
            last_wallet_amt   = get_prev_val('Wallet_Amount', is_float=True)

    st.divider()

    c_notes, c_coins, c_totals = st.columns([1, 1, 1.5])
    
    with c_notes:
        st.markdown("#### 💵 :green[Notes Entry]")
        notes_500 = st.number_input("₹500", min_value=0, step=1, value=last_notes['500'])
        notes_200 = st.number_input("₹200", min_value=0, step=1, value=last_notes['200'])
        notes_100 = st.number_input("₹100", min_value=0, step=1, value=last_notes['100'])
        notes_50  = st.number_input("₹50", min_value=0, step=1, value=last_notes['50'])
        notes_20  = st.number_input("₹20", min_value=0, step=1, value=last_notes['20'])
        notes_10  = st.number_input("₹10 (Note)", min_value=0, step=1, value=last_notes['10_Note']) 

    with c_coins:
        st.markdown("#### 🪙 :orange[Coins Entry]")
        coins_10  = st.number_input("₹10 (Coin)", min_value=0, step=1, value=last_notes['10_Coin']) 
        notes_5   = st.number_input("₹5", min_value=0, step=1, value=last_notes['5'])
        notes_2   = st.number_input("₹2", min_value=0, step=1, value=last_notes['2'])
        notes_1   = st.number_input("₹1", min_value=0, step=1, value=last_notes['1'])

    with c_totals:
        st.markdown("#### 🧾 Additional & Totals")
        wallet_val = st.number_input("Lump Sum Amount (₹)", min_value=0.0, step=10.0, value=float(last_wallet_amt))
        
        st.divider()
        
        total_notes = (notes_500 * 500) + (notes_200 * 200) + (notes_100 * 100) + (notes_50 * 50) + (notes_20 * 20) + (notes_10 * 10)
        total_coins = (coins_10 * 10) + (notes_5 * 5) + (notes_2 * 2) + (notes_1 * 1)
        total_cash = total_notes + total_coins + wallet_val
        
        st.markdown("### Breakdown")
        
        html_metrics = f"""
        <div style="display: flex; gap: 10px; margin-bottom: 15px;">
            <div style="flex: 1; background-color: rgba(76, 175, 80, 0.15); padding: 10px; border-radius: 8px; border-left: 5px solid #4caf50;">
                <p style="margin:0px; font-size:14px; font-weight: bold; color: #4caf50;">💵 Total Notes</p>
                <h3 style="margin:0px; padding-top: 5px;">₹ {total_notes:,.2f}</h3>
            </div>
            <div style="flex: 1; background-color: rgba(255, 152, 0, 0.15); padding: 10px; border-radius: 8px; border-left: 5px solid #ff9800;">
                <p style="margin:0px; font-size:14px; font-weight: bold; color: #ff9800;">🪙 Total Coins</p>
                <h3 style="margin:0px; padding-top: 5px;">₹ {total_coins:,.2f}</h3>
            </div>
        </div>
        """
        st.markdown(html_metrics, unsafe_allow_html=True)
        st.metric("Overall Physical Cash", f"₹ {total_cash:,.2f}")

    st.divider()
    c_rem, c_btn = st.columns([2, 1])
    with c_rem: cash_remark = st.text_input("Remark (Optional)")
    with c_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save Cash Count", use_container_width=True, type="primary"):
            if not wallet_name:
                st.warning("⚠️ Please specify a Wallet Name.")
            else:
                time_now = get_ist_now()
                today_str = time_now.strftime("%d-%m-%Y")
                time_str = time_now.strftime("%H:%M")
                
                row_data = [
                    today_str, time_str, total_cash, 
                    notes_500, notes_200, notes_100, notes_50, notes_20, 
                    notes_10, coins_10,  
                    notes_5, notes_2, notes_1, 
                    wallet_name, wallet_val, cash_remark
                ]
                try:
                    sh.worksheet("CASH_COUNT").append_row(row_data)
                    load_cash_data.clear()
                    st.success(f"Successfully saved cash count of ₹{total_cash} to {wallet_name}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving to Google Sheets: {e}")

    st.divider()
    st.subheader("📜 Recent Cash Counts")
    if not df_cash.empty:
        desired_cols = ['Date', 'Time', 'Total', 'Wallet_Name', 'Wallet_Amount', 'Remark']
        display_cols = [c for c in desired_cols if c in df_cash.columns]
        if not display_cols: display_cols = df_cash.columns
        display_df = df_cash[display_cols].tail(10).iloc[::-1]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No past cash counts found yet.")

    st.divider()
    st.header("🏦 Master Account Reconciliation")
    st.write("Review all your balances at a glance. Edit the 'Actual Balance' if it differs from the Ledger, then click the button to auto-adjust.")
    
    df_money = load_money_data()
    ledger_balances = {}
    
    if not df_money.empty and 'Account' in df_money.columns:
        df_m_clean = df_money[df_money['Remark'] != '⚠️ INCOMPLETE'].copy()
        df_m_clean['In'] = pd.to_numeric(df_m_clean['In'].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        df_m_clean['Out'] = pd.to_numeric(df_m_clean['Out'].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        
        acc_summary = df_m_clean.groupby('Account').agg({'In': 'sum', 'Out': 'sum'}).reset_index()
        acc_summary['Balance'] = acc_summary['In'] - acc_summary['Out']
        ledger_balances = dict(zip(acc_summary['Account'], acc_summary['Balance']))

    # EXTRACT LATEST CASH COUNTS
    latest_cash_counts = {}
    if not df_cash.empty and 'Wallet_Name' in df_cash.columns and 'Total' in df_cash.columns:
        last_counts = df_cash.drop_duplicates(subset=['Wallet_Name'], keep='last')
        for _, row in last_counts.iterrows():
            try: latest_cash_counts[str(row['Wallet_Name']).strip()] = float(row['Total'])
            except: pass

    acc_opts = get_clean_accounts()
    all_accounts = list(dict.fromkeys(acc_opts + list(ledger_balances.keys())))
    all_accounts = [a for a in all_accounts if str(a).strip() != "" and a not in ACCOUNT_HEADERS]

    st.markdown("---")
    h1, h2, h3, h4 = st.columns([1.5, 1, 1.2, 1.3])
    h1.markdown("**Account Name**")
    h2.markdown("**Ledger Balance**")
    h3.markdown("**Actual Balance**")
    h4.markdown("**Status / Action**")
    st.markdown("---")

    for idx, acc in enumerate(all_accounts):
        l_bal = float(ledger_balances.get(acc, 0.0))
        
        # SMART DEFAULT: IF WE HAVE A CASH COUNT, USE IT AS THE DEFAULT ACTUAL BALANCE
        default_act_bal = latest_cash_counts.get(acc, l_bal)
        
        c1, c2, c3, c4 = st.columns([1.5, 1, 1.2, 1.3])
        c1.write(f"**{acc}**")
        c2.write(f"₹ {l_bal:,.2f}")
        
        actual_bal = c3.number_input(
            f"Actual {acc}", value=float(default_act_bal), step=100.0, key=f"act_bal_{idx}", label_visibility="collapsed"
        )
        
        difference = actual_bal - l_bal
        with c4:
            if difference == 0:
                st.markdown("✅ Synced")
            else:
                btn_label = f"⚡ Adjust (₹{difference:+,.2f})"
                if st.button(btn_label, key=f"adj_btn_{idx}", type="primary"):
                    try:
                        time_now = get_ist_now()
                        today_str = time_now.strftime("%d-%m-%Y")
                        time_str = time_now.strftime("%H:%M")
                        adj_in = abs(difference) if difference > 0 else ""
                        adj_out = abs(difference) if difference < 0 else ""
                        row_data = [
                            today_str, time_str, adj_in, adj_out, acc, "Salary", "PERS", "System Adjustment", 
                            "Ledger Correction", f"Pre-Sync {acc} Balance", "", "", "Temporary adjustment pending SK-Sync migration"
                        ]
                        sh.worksheet("MONEY_DATA").append_row(row_data)
                        load_money_data.clear()
                        st.success(f"Successfully adjusted {acc}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error applying adjustment: {e}")

# ==========================================
# TAB 2: SHOPPING LIST
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
            
        # DYNAMIC ITEM AGGREGATION FROM HISTORY
        if not p_sub_df.empty and 'Map_Particular' in p_sub_df.columns:
            base_opts = list(dict.fromkeys([str(p).strip() for p in p_sub_df['Map_Particular'].dropna() if str(p).strip() != ""]))
        else:
            base_opts = get_list("Particulars")
            
        # Pull previously added items from SHOPPING_LIST to build the memory dropdown
        df_shop_hist = load_shopping_data()
        past_items = []
        if not df_shop_hist.empty and 'Item' in df_shop_hist.columns:
            past_items = [str(x).strip() for x in df_shop_hist['Item'].dropna().tolist() if str(x).strip() != ""]
            
        # Merge CONFIG options and historical items, removing duplicates
        p_part_opts = list(dict.fromkeys(base_opts + past_items))
            
        selected_items = st.multiselect("Select Existing Items", p_part_opts, key="plan_item_multi")
        custom_items_str = st.text_input("Add New Items (Separate with commas, e.g. Apples, Milk)", key="plan_item_new_multi")
        
    with col2:
        shop_type_opts = []
        if 'Shop_Type' in config_df.columns:
            shop_type_opts = list(dict.fromkeys([str(s).strip() for s in config_df['Shop_Type'].dropna() if str(s).strip() != ""]))
        if not shop_type_opts: shop_type_opts = ["Grocery", "Vegetables", "Stationary", "Hardware", "Medicine"]
            
        s_type = st.selectbox("Shop Category", shop_type_opts + ["-- Type New --"], key="plan_stype")
        if s_type == "-- Type New --": s_type = st.text_input("Type New Shop Category", key="plan_stype_new")
            
        fund = st.selectbox("Fund to use", get_list("Funds"), key="plan_fund")
        account = st.selectbox("Account to use", get_clean_accounts(), key="plan_acc")
        
    if st.button("➕ Add All to Pending List", use_container_width=True):
        all_items = selected_items + [i.strip() for i in custom_items_str.split(',') if i.strip()]
        if all_items:
            try:
                today_str = get_ist_now().strftime("%d-%m-%Y")
                # Removed Est_Cost logic and passing a blank string to the sheet
                rows_to_add = [[today_str, itm, s_type, "", "", "Pending", "", fund, account] for itm in all_items]
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
            display_cols = [c for c in ['Item', 'Shop_Type', 'Fund', 'Account'] if c in all_pending.columns]
            st.dataframe(all_pending[display_cols], use_container_width=True, hide_index=True)
        else: st.write("You have no pending items!")

# ==========================================
# TAB 3: MONTHLY PAYMENT CHECKLIST
# ==========================================
with tab_bills:
    st.header("✅ Monthly Payment Checklist")
    
    current_month_str = get_ist_now().strftime("%B %Y")
    
    target_month_opts = []
    now_dt = get_ist_now()
    for i in range(12):
        m = now_dt.month + i
        y = now_dt.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        target_month_opts.append(date(y, m, 1).strftime("%B %Y"))
    
    df_bills = load_bills_data()
    
    with st.expander("➕ Add New Bill to Checklist"):
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            default_add_idx = target_month_opts.index(current_month_str) if current_month_str in target_month_opts else 0
            bill_month = st.selectbox("Target Month", target_month_opts, index=default_add_idx, key="add_mon")
            bill_name = st.text_input("Bill Name (e.g., Electricity, Credit Card)")
            bill_type = st.selectbox("Bill Type", ["SCHOOL", "PERS", "OTHER"])
        with b_col2:
            bill_amt = st.number_input("Estimated Amount (₹)", min_value=0.0, step=100.0)
            bill_due = st.date_input("Due Date", value=st.session_state.locked_date)
            bill_fund = st.selectbox("Default Fund", get_list("Funds"), key="bill_fund")
            bill_acc = st.selectbox("Default Account", get_clean_accounts(), key="bill_acc")
            
        if st.button("Save to Checklist", use_container_width=True):
            if bill_name:
                sh.worksheet("PAYMENT_CHECKLIST").append_row([
                    bill_month, bill_name, bill_type, bill_amt, bill_due.strftime("%d-%m-%Y"), 
                    "Pending", bill_fund, bill_acc, ""
                ])
                load_bills_data.clear()
                st.success(f"{bill_name} added for {bill_month}!")
                st.rerun()
            else:
                st.warning("Please enter a Bill Name.")

    st.divider()

    st.subheader("⏳ Pending Payments")
    
    pending_bills = pd.DataFrame()
    if not df_bills.empty and 'Status' in df_bills.columns:
        pending_bills = df_bills[df_bills['Status'] == 'Pending'].copy()
        
    if not pending_bills.empty:
        bills_ws = sh.worksheet("PAYMENT_CHECKLIST")
        
        def parse_month(m_str):
            try: return datetime.strptime(str(m_str), "%B %Y")
            except: return datetime(1900, 1, 1)
            
        pending_bills['Sort_Date'] = pending_bills['Month'].apply(parse_month)
        pending_bills = pending_bills.sort_values(['Sort_Date', 'Due_Date'])
        
        for month_name, group in pending_bills.groupby('Month', sort=False):
            st.markdown(f"#### 🗓️ Tracking for: {month_name}")
            
            for idx, row in group.iterrows():
                sheet_row = idx + 2 
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1.2, 1.3])
                    with c1:
                        st.write(f"**{row.get('Bill_Name', 'Unknown')}** ({row.get('Type', '')})")
                        due_status = f"🔴 Due: {row.get('Due_Date', '')}" 
                        st.caption(f"{due_status} | Fund: {row.get('Fund', '')}")
                    with c2:
                        raw_amt = row.get('Est_Amount', 0)
                        try: safe_amt = float(raw_amt) if str(raw_amt).strip() != "" else 0.0
                        except (ValueError, TypeError): safe_amt = 0.0
                            
                        pay_amt = st.number_input(
                            "Pay Amount", 
                            value=safe_amt, 
                            key=f"payamt_{idx}", 
                            label_visibility="collapsed"
                        )
                        auto_renew = st.checkbox("🔁 Auto-Renew", value=True, key=f"renew_{idx}")
                        
                    with c3:
                        pay_clicked = st.button("💸 Pay & Log", key=f"paybtn_{idx}", use_container_width=True, type="primary")

                    due_date_str = str(row.get('Due_Date', ''))
                    next_due_date_obj = st.session_state.locked_date
                    try:
                        dt = datetime.strptime(due_date_str, "%d-%m-%Y")
                        nm = dt.month + 1 if dt.month < 12 else 1
                        ny = dt.year if dt.month < 12 else dt.year + 1
                        max_day = calendar.monthrange(ny, nm)[1]
                        nd = min(dt.day, max_day)
                        next_due_date_obj = date(ny, nm, nd)
                    except: pass
                        
                    curr_month_str_bill = str(row.get('Month', ''))
                    next_month_str_default = curr_month_str_bill
                    try:
                        mt = datetime.strptime(curr_month_str_bill, "%B %Y")
                        nm_m = mt.month + 1 if mt.month < 12 else 1
                        nm_y = mt.year if mt.month < 12 else mt.year + 1
                        next_month_str_default = date(nm_y, nm_m, 1).strftime("%B %Y")
                    except: pass

                    rev_month = next_month_str_default
                    rev_amt = safe_amt
                    rev_due = next_due_date_obj

                    if auto_renew:
                        with st.expander("⚙️ Review Next Cycle Settings", expanded=False):
                            r_c1, r_c2, r_c3 = st.columns(3)
                            with r_c1: rev_month = st.text_input("Next Month", value=next_month_str_default, key=f"rmon_{idx}")
                            with r_c2: rev_amt = st.number_input("Next Est. Amount", value=float(safe_amt), step=100.0, key=f"ramt_{idx}")
                            with r_c3: rev_due = st.date_input("Next Due Date", value=next_due_date_obj, key=f"rdue_{idx}")

                    if pay_clicked:
                        try:
                            b_name = str(row.get('Bill_Name', ''))
                            b_type = str(row.get('Type', 'PERS'))
                            
                            time_now = get_ist_now()
                            today_str = time_now.strftime("%d-%m-%Y")
                            time_str = time_now.strftime("%H:%M")
                            
                            match_row = config_df[config_df['Map_Particular'].astype(str).str.strip() == b_name]
                            cat = str(match_row['Map_Category'].values[0]) if not match_row.empty else "NEEDS"
                            subcat = str(match_row['Map_SubCat'].values[0]) if not match_row.empty else ""
                            
                            loc_val = current_loc or ""
                            tf_val = loc_val if should_inject_tofrom(loc_val) else ""
                            
                            money_row = [
                                today_str, time_str, "", pay_amt, 
                                str(row.get('Account', '')), str(row.get('Fund', '')), 
                                b_type, cat, subcat, b_name, 
                                tf_val, loc_val, "Cleared via Bill Checklist"
                            ]
                            sh.worksheet("MONEY_DATA").append_row(money_row)
                            
                            headers = bills_ws.row_values(1)
                            bills_ws.update_cell(sheet_row, headers.index('Status') + 1, 'Paid')
                            bills_ws.update_cell(sheet_row, headers.index('Actual_Paid') + 1, pay_amt)
                            
                            if auto_renew:
                                bills_ws.append_row([
                                    rev_month, b_name, b_type, rev_amt, rev_due.strftime("%d-%m-%Y"), 
                                    "Pending", str(row.get('Fund', '')), str(row.get('Account', '')), ""
                                ])

                            load_money_data.clear()
                            load_bills_data.clear()
                            st.success(f"Payment logged! Next bill generated for {rev_month}." if auto_renew else f"Payment logged for {b_name}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error processing payment: {e}")
    else:
        st.info("🎉 All caught up! No pending bills for now.")

    st.divider()
    with st.expander("📜 View Paid Bills History & Renew"):
        if not df_bills.empty and 'Status' in df_bills.columns:
            paid_bills = df_bills[df_bills['Status'] == 'Paid']
            
            if not paid_bills.empty:
                display_cols = ['Month', 'Bill_Name', 'Type', 'Actual_Paid', 'Fund', 'Account']
                st.dataframe(paid_bills[display_cols], use_container_width=True, hide_index=True)
                
                st.divider()
                
                st.markdown("#### 🔁 Renew a Past Bill")
                st.caption("Manually re-queue a previously paid bill for its next cycle.")
                
                past_bill_names_all = list(paid_bills['Bill_Name'].unique())
                pending_names = pending_bills['Bill_Name'].unique() if not pending_bills.empty else []
                past_bill_names = [b for b in past_bill_names_all if b not in pending_names]
                
                if past_bill_names:
                    r_col1, r_col2 = st.columns([1.5, 1])
                    with r_col1:
                        sel_bill_name = st.selectbox("Select Past Bill", past_bill_names)
                    with r_col2:
                        bill_data = paid_bills[paid_bills['Bill_Name'] == sel_bill_name].iloc[-1]
                        bill_type = bill_data.get('Type', 'PERS')
                        bill_fund = bill_data.get('Fund', '')
                        bill_acc = bill_data.get('Account', '')
                        
                        raw_last_amt = bill_data.get('Actual_Paid', 0)
                        try: last_paid_amt = float(raw_last_amt) if str(raw_last_amt).strip() != "" else 0.0
                        except: last_paid_amt = 0.0
                        
                        st.info(f"Type: {bill_type} | Last Paid: ₹{last_paid_amt}")

                    rn_col1, rn_col2, rn_col3 = st.columns(3)
                    with rn_col1:
                        default_rn_idx = target_month_opts.index(current_month_str) if current_month_str in target_month_opts else 0
                        new_month = st.selectbox("Target Month", target_month_opts, index=default_rn_idx, key="rn_mon")
                    with rn_col2:
                        new_amt = st.number_input("Est. Amount", value=last_paid_amt, step=100.0, key="rn_amt")
                    with rn_col3:
                        new_due = st.date_input("Next Due Date", value=st.session_state.locked_date, key="rn_due")

                    if st.button(f"➕ Add '{sel_bill_name}' back to Pending", type="primary", use_container_width=True):
                        try:
                            sh.worksheet("PAYMENT_CHECKLIST").append_row([
                                new_month, sel_bill_name, bill_type, new_amt, new_due.strftime("%d-%m-%Y"), 
                                "Pending", bill_fund, bill_acc, ""
                            ])
                            load_bills_data.clear()
                            st.success(f"{sel_bill_name} has been renewed and added to your Pending list!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error renewing bill: {e}")
                else:
                    st.success("All your past bills are currently active in the Pending list!")
            else:
                st.info("No paid bills recorded yet.")

# ==========================================
# TAB 4: ADVANCED ERP DASHBOARD
# ==========================================
with tab_dash:
    st.header("📊 Financial Intelligence")
    
    # --- BIKE MILEAGE ANALYTICS ---
    df_bike = load_bike_data()
    if not df_bike.empty and len(df_bike) > 1:
        st.subheader("🏍️ Bike Mileage Analytics")
        try:
            df_b = df_bike.copy()
            df_b['Odometer'] = pd.to_numeric(df_b['Odometer'])
            df_b['Litres'] = pd.to_numeric(df_b['Litres'])
            df_b['Date_Obj'] = pd.to_datetime(df_b['Date'], format='%d-%m-%Y', errors='coerce')
            
            # Calculate distance covered since LAST log and divide by LAST log's litres
            df_b['Prev_Odo'] = df_b['Odometer'].shift(1)
            df_b['Prev_Litres'] = df_b['Litres'].shift(1)
            df_b['Distance_Covered'] = df_b['Odometer'] - df_b['Prev_Odo']
            df_b['Mileage'] = df_b['Distance_Covered'] / df_b['Prev_Litres']
            
            # Date gaps
            df_b['Days_Gap'] = df_b['Date_Obj'].diff().dt.days
            
            latest_mileage = df_b.iloc[-1]['Mileage']
            total_dist = df_b.iloc[-1]['Odometer'] - df_b.iloc[0]['Odometer']
            
            # Average calculation: Total distance / Total fuel burned (excluding fuel just bought)
            total_litres_consumed = df_b['Prev_Litres'].sum()
            avg_mileage = total_dist / total_litres_consumed if total_litres_consumed > 0 else 0.0
            
            avg_gap = df_b['Days_Gap'].mean()
            latest_gap = df_b.iloc[-1]['Days_Gap']
            
            last_date = df_b.iloc[-1]['Date_Obj']
            days_since_last = (get_ist_now().date() - last_date.date()).days
            
            safe_avg_gap = f"{avg_gap:.1f} days" if pd.notnull(avg_gap) else "N/A"
            safe_latest_gap = f"{latest_gap:.0f} days" if pd.notnull(latest_gap) else "N/A"
            
            c_m1, c_m2, c_m3 = st.columns(3)
            c_m1.metric("Latest Mileage", f"{latest_mileage:.1f} km/L")
            c_m2.metric("Avg Mileage", f"{avg_mileage:.1f} km/L")
            c_m3.metric("Total Distance", f"{total_dist} km")
            
            c_g1, c_g2, c_g3 = st.columns(3)
            c_g1.metric("Avg Refuel Interval", safe_avg_gap)
            c_g2.metric("Previous Refuel Gap", safe_latest_gap)
            c_g3.metric("Current Tank Status", f"Last: {days_since_last} d ago")
            
            fig_mileage = px.line(df_b.dropna(subset=['Mileage']), x='Date', y='Mileage', markers=True, title="Mileage Trend Over Time", color_discrete_sequence=['#ff9800'])
            st.plotly_chart(fig_mileage, use_container_width=True)
            st.divider()
        except Exception as e:
            st.caption(f"Waiting for more data to display mileage chart... ({e})")
            st.divider()
    
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
    st.write("Ensure your Google Sheet matches the required tab and column structures.")
