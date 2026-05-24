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
df_shop = load_shopping_data()

# ==========================================
# MAIN APP
# ==========================================
st.title("🛒 Shopping List Manager")

# 1. Shop Category (Dropdown from CONFIG)
shop_type_opts = sorted(list(dict.fromkeys([str(s).strip() for s in config_df['Shop_Type'].dropna() if str(s).strip() != ""]))) if 'Shop_Type' in config_df.columns else ["Grocery", "Vegetables", "Stationary"]
s_type = st.selectbox("1. Shop Category", shop_type_opts)

# 2. Sub Category (Dropdown from CONFIG)
subcat_opts = sorted(list(dict.fromkeys([str(s).strip() for s in config_df['Map_SubCat'].dropna() if str(s).strip() != ""])))
p_subcat = st.selectbox("2. Sub Category", subcat_opts)

# 3. Existing Items (Filtered by Selected Shop_Type)
# We look at SHOPPING_LIST tab, filter by Shop_Type, then pull unique Items
if not df_shop.empty and 'Shop_Type' in df_shop.columns and 'Item' in df_shop.columns:
    items_in_shop = df_shop[df_shop['Shop_Type'].astype(str).str.strip() == s_type]
    past_items = sorted(list(dict.fromkeys([str(x).strip() for x in items_in_shop['Item'].dropna() if str(x).strip() != ""])))
else:
    past_items = []

selected_items = st.multiselect("3. Select Existing Items", past_items)
custom_items_str = st.text_input("Add New Items (Comma separated)")

# --- SAVE LOGIC ---
if st.button("➕ Add All to Pending List", use_container_width=True, type="primary"):
    all_items = selected_items + [i.strip() for i in custom_items_str.split(',') if i.strip()]
    if all_items:
        try:
            today_str = get_ist_now().strftime("%d-%m-%Y")
            
            # HARDCODED DEFAULTS:
            # Date_Added, Item, Shop_Type, Est_Cost, Actual_Cost, Status, Date_Bought (Mapped to SubCat), Fund, Account
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

# Reload data after potential save
df_shop_new = load_shopping_data()
if not df_shop_new.empty:
    pending = df_shop_new[df_shop_new['Status'] == 'Pending']
    
    if not pending.empty:
        # Dynamic header check to prevent crashes
        potential_cols = ['Item', 'Shop_Type', 'Date_Bought', 'Fund', 'Account']
        found_cols = [c for c in potential_cols if c in pending.columns]
        
        df_display = pending[found_cols].copy()
        
        # Rename 'Date_Bought' to 'Sub Category' for UI
        if 'Date_Bought' in df_display.columns:
            df_display.rename(columns={'Date_Bought': 'Sub Category'}, inplace=True)
            
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.write("You have no pending items!")
