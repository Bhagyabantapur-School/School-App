import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone, date
import calendar
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="Shopping & Finance", page_icon="🛒", layout="centered")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

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

# --- CACHING ---
@st.cache_data(ttl=60)
def load_config():
    try: return pd.DataFrame(sh.worksheet("CONFIG").get_all_records())
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

config_df = load_config()

# --- HELPERS ---
def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

def get_clean_accounts():
    raw = get_list("Accounts")
    return [a for a in raw if a not in ["A. Cash:", "B. Bank Accounts:", "C. Credit Cards:", "D. Digital Wallet:", "E. Loan:", "F. Members:"]]

# ==========================================
# MAIN LAYOUT
# ==========================================
st.title("🛒 Shopping & Finance")
tab_shopping, tab_cash, tab_bills, tab_dash = st.tabs(["🛒 Shopping", "💵 Cash", "✅ Bills", "📊 Analytics"])

# ==========================================
# TAB: SHOPPING
# ==========================================
with tab_shopping:
    st.subheader("➕ Plan Multiple Purchases")
    
    col1, col2 = st.columns(2)
    with col1:
        # Entity / Category Mapping
        mapped_entities = list(dict.fromkeys([str(e).strip() for e in config_df['Map_Entity'].dropna() if str(e).strip() != ""])) if 'Map_Entity' in config_df.columns else get_list("Entities")
        p_entity = st.selectbox("Entity", mapped_entities, key="plan_ent")
        
        if 'Map_Entity' in config_df.columns:
            p_ent_df = config_df[config_df['Map_Entity'].astype(str).str.strip() == p_entity]
            p_cat_opts = list(dict.fromkeys([str(c).strip() for c in p_ent_df['Map_Category'].dropna() if str(c).strip() != ""]))
            p_category = st.selectbox("Category", p_cat_opts + ["-- Type New --"], key="plan_cat")
            p_cat_df = p_ent_df[p_ent_df['Map_Category'].astype(str).str.strip() == p_category] if p_category != "-- Type New --" else pd.DataFrame()
        else:
            p_category = st.selectbox("Category", get_list("Categories") + ["-- Type New --"], key="plan_cat_fb")
            p_cat_df = pd.DataFrame()
            
        # Items Memory Logic: Merge CONFIG and Past History
        base_opts = list(dict.fromkeys([str(p).strip() for p in p_cat_df['Map_Particular'].dropna() if str(p).strip() != ""])) if not p_cat_df.empty else get_list("Particulars")
        df_shop_hist = load_shopping_data()
        past_items = [str(x).strip() for x in df_shop_hist['Item'].dropna().tolist() if str(x).strip() != ""] if not df_shop_hist.empty else []
        p_part_opts = list(dict.fromkeys(base_opts + past_items))
            
        selected_items = st.multiselect("Select Existing Items", p_part_opts, key="plan_item_multi")
        custom_items_str = st.text_input("Add New Items (Comma separated)", key="plan_item_new_multi")
        
    with col2:
        shop_type_opts = list(dict.fromkeys([str(s).strip() for s in config_df['Shop_Type'].dropna() if str(s).strip() != ""])) if 'Shop_Type' in config_df.columns else ["Grocery", "Vegetables", "Stationary"]
        s_type = st.selectbox("Shop Category", shop_type_opts + ["-- Type New --"], key="plan_stype")
        fund = st.selectbox("Fund to use", get_list("Funds"), key="plan_fund")
        account = st.selectbox("Account to use", get_clean_accounts(), key="plan_acc")
        
    if st.button("➕ Add All to Pending List", use_container_width=True, type="primary"):
        all_items = selected_items + [i.strip() for i in custom_items_str.split(',') if i.strip()]
        if all_items:
            try:
                today_str = get_ist_now().strftime("%d-%m-%Y")
                # Est_Cost removed as requested
                rows_to_add = [[today_str, itm, s_type, "", "", "Pending", "", fund, account] for itm in all_items]
                sh.worksheet("SHOPPING_LIST").append_rows(rows_to_add)
                load_shopping_data.clear() 
                st.success(f"Added {len(all_items)} items to your {s_type} list!")
                st.rerun()
            except Exception as e: st.error(f"Failed to save: {e}")
        else: st.warning("⚠️ Please select or type items.")

    st.divider()
    st.subheader("📋 All Pending Items")
    df_shop = load_shopping_data()
    if not df_shop.empty:
        st.dataframe(df_shop[df_shop['Status'] == 'Pending'][['Item', 'Shop_Type', 'Fund', 'Account']], use_container_width=True, hide_index=True)

# ==========================================
# TABS 2-4 (Cash, Bills, Analytics)
# ==========================================
# (You can copy the code for these specific tabs from your previous money_utilities.py here)
with tab_cash:
    st.info("Cash tab logic placeholder - Copy from money_utilities.py")
with tab_bills:
    st.info("Bills tab logic placeholder - Copy from money_utilities.py")
with tab_dash:
    st.info("Analytics tab logic placeholder - Copy from money_utilities.py")
