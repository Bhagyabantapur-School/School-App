import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# SETUP & CONNECTION
# ==========================================
st.set_page_config(page_title="Shopping List Manager", page_icon="🛒", layout="centered")

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
def load_shopping_data():
    try: return pd.DataFrame(sh.worksheet("SHOPPING_LIST").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

# --- FILTERING LOGIC ---
def get_dependent_options(df, target_col, filter_col=None, filter_val=None):
    subset = df
    if filter_col and filter_val:
        subset = df[df[filter_col].astype(str).str.strip() == str(filter_val).strip()]
    options = sorted(list(dict.fromkeys([str(x).strip() for x in subset[target_col].dropna() if str(x).strip() != ""])))
    return options

# ==========================================
# MAIN APP
# ==========================================
st.title("🛒 Shopping List Manager")

# 1. Shop Category
shop_type_opts = list(dict.fromkeys([str(s).strip() for s in config_df['Shop_Type'].dropna() if str(s).strip() != ""])) if 'Shop_Type' in config_df.columns else ["Grocery", "Vegetables", "Stationary"]
s_type = st.selectbox("1. Shop Category", shop_type_opts, index=0)

# 2. Sub Category (Dependent on CONFIG)
subcat_opts = get_dependent_options(config_df, 'Map_SubCat')
default_sub = "GROC" if "GROC" in subcat_opts else (subcat_opts[0] if subcat_opts else None)
p_subcat = st.selectbox("2. Sub Category", subcat_opts, index=subcat_opts.index(default_sub) if default_sub else 0)

# 3. Particulars (Dependent on Sub Category + History)
config_items = get_dependent_options(config_df, 'Map_Particular', 'Map_SubCat', p_subcat)
df_shop_hist = load_shopping_data()
past_items = [str(x).strip() for x in df_shop_hist['Item'].dropna().tolist() if str(x).strip() != ""] if not df_shop_hist.empty else []
p_part_opts = sorted(list(dict.fromkeys(config_items + past_items)))

selected_items = st.multiselect("3. Select Existing Items", p_part_opts)
custom_items_str = st.text_input("Add New Items (Comma separated)")

# --- SAVE LOGIC ---
if st.button("➕ Add All to Pending List", use_container_width=True, type="primary"):
    all_items = selected_items + [i.strip() for i in custom_items_str.split(',') if i.strip()]
    if all_items:
        try:
            today_str = get_ist_now().strftime("%d-%m-%Y")
            # HARDCODED DEFAULTS: 
            # Date_Added, Item, Shop_Type, Est_Cost, Actual_Cost, Status, Date_Bought (SubCat), Fund, Account
            rows_to_add = [[today_str, itm, s_type, "", "", "Pending", p_subcat, "Salary", "AXIS Bank"] for itm in all_items]
            
            sh.worksheet("SHOPPING_LIST").append_rows(rows_to_add)
            load_shopping_data.clear() 
            st.success(f"Added {len(all_items)} items!")
            st.rerun()
        except Exception as e: st.error(f"Failed to save: {e}")
    else: st.warning("⚠️ Please select or type items.")

# --- PENDING LIST ---
st.divider()
st.subheader("📋 Pending Items")
df_shop = load_shopping_data()

if not df_shop.empty:
    pending = df_shop[df_shop['Status'] == 'Pending']
    
    if not pending.empty:
        # Check available columns and map Date_Bought to 'Sub Category'
        potential_cols = ['Item', 'Shop_Type', 'Date_Bought', 'Fund', 'Account']
        found_cols = [c for c in potential_cols if c in pending.columns]
        
        df_display = pending[found_cols].copy()
        if 'Date_Bought' in df_display.columns:
            df_display.rename(columns={'Date_Bought': 'Sub Category'}, inplace=True)
            
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.write("You have no pending items!")
