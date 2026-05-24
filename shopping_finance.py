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

# ==========================================
# MAIN APP
# ==========================================
st.title("🛒 Shopping List Manager")
st.subheader("➕ Plan New Purchases")

# Load Past Items for Memory
df_shop_hist = load_shopping_data()
past_items = [str(x).strip() for x in df_shop_hist['Item'].dropna().tolist() if str(x).strip() != ""] if not df_shop_hist.empty else []
p_part_opts = sorted(list(dict.fromkeys(past_items)))

# --- INPUTS ---
# Sub Category Dropdown
sub_cat_opts = [str(s).strip() for s in config_df['Sub-Categories'].dropna().tolist() if str(s).strip() != ""] if 'Sub-Categories' in config_df.columns else ["GROC", "VEGE", "MISC"]
default_idx = sub_cat_opts.index("GROC") if "GROC" in sub_cat_opts else 0
p_sub_cat = st.selectbox("Sub Category", sub_cat_opts, index=default_idx)

selected_items = st.multiselect("Select Existing Items", p_part_opts)
custom_items_str = st.text_input("Add New Items (Comma separated)")

# --- SAVE LOGIC ---
if st.button("➕ Add All to Pending List", use_container_width=True, type="primary"):
    all_items = selected_items + [i.strip() for i in custom_items_str.split(',') if i.strip()]
    if all_items:
        try:
            today_str = get_ist_now().strftime("%d-%m-%Y")
            
            # HARDCODED DEFAULTS:
            # Order: Date_Added, Item, Shop_Type, Est_Cost, Actual_Cost, Status, Date_Bought, Fund, Account
            # Note: We map p_sub_cat (Sub Category) to the 'Date_Bought' field as per your requirement
            rows_to_add = [[today_str, itm, "Grocery", "", "", "Pending", p_sub_cat, "Salary", "AXIS Bank"] for itm in all_items]
            
            sh.worksheet("SHOPPING_LIST").append_rows(rows_to_add)
            load_shopping_data.clear() 
            st.success(f"Added {len(all_items)} items to your list!")
            st.rerun()
        except Exception as e: st.error(f"Failed to save: {e}")
    else: st.warning("⚠️ Please select or type items.")

# --- PENDING LIST DISPLAY ---
st.divider()
st.subheader("📋 Pending Items")
df_shop = load_shopping_data()

if not df_shop.empty:
    # Filter for pending items
    pending = df_shop[df_shop['Status'] == 'Pending']
    
    if not pending.empty:
        # Smart selection: only show columns that exist in your sheet
        potential_cols = ['Item', 'Shop_Type', 'Date_Bought', 'Fund', 'Account']
        found_cols = [c for c in potential_cols if c in pending.columns]
        
        df_display = pending[found_cols].copy()
        
        # Rename 'Date_Bought' to 'Sub Category' for display
        if 'Date_Bought' in df_display.columns:
            df_display.rename(columns={'Date_Bought': 'Sub Category'}, inplace=True)
            
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.write("You have no pending items!")
