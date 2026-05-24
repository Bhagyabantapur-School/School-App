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

# --- HIERARCHICAL DROPDOWNS ---
st.subheader("⚙️ Hierarchy Selection")

# 1. Entity
entities = get_dependent_options(config_df, 'Map_Entity')
default_ent = "PERS" if "PERS" in entities else (entities[0] if entities else None)
p_entity = st.selectbox("1. Entity", entities, index=entities.index(default_ent) if default_ent else 0)

# 2. Category
categories = get_dependent_options(config_df, 'Map_Category', 'Map_Entity', p_entity)
default_cat = "NEEDS" if "NEEDS" in categories else (categories[0] if categories else None)
p_category = st.selectbox("2. Category", categories, index=categories.index(default_cat) if default_cat else 0)

# 3. Sub Category
subcats = get_dependent_options(config_df, 'Map_SubCat', 'Map_Category', p_category)
default_sub = "GROC" if "GROC" in subcats else (subcats[0] if subcats else None)
p_subcat = st.selectbox("3. Sub Category", subcats, index=subcats.index(default_sub) if default_sub else 0)

# 4. Particulars (Existing Items)
particulars = get_dependent_options(config_df, 'Map_Particular', 'Map_SubCat', p_subcat)
selected_items = st.multiselect("4. Select Existing Items", particulars)
custom_items_str = st.text_input("Add New Items (Comma separated)")

# --- SAVE LOGIC ---
if st.button("➕ Add All to Pending List", use_container_width=True, type="primary"):
    all_items = selected_items + [i.strip() for i in custom_items_str.split(',') if i.strip()]
    if all_items:
        try:
            today_str = get_ist_now().strftime("%d-%m-%Y")
            # Defaults: Entity=p_entity, Category=p_category, SubCat=p_subcat, Shop=Grocery, Fund=Salary, Account=AXIS Bank
            # Appending rows: Date, Item, Shop_Type, Est_Cost, Actual_Cost, Status, Date_Bought, Fund, Account
            # Mapping SubCat to Date_Bought column as before
            rows_to_add = [[today_str, itm, "Grocery", "", "", "Pending", p_subcat, "Salary", "AXIS Bank"] for itm in all_items]
            
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
        # Show items and map the Note/Date_Bought back to Sub Category
        df_display = pending[['Item', 'Shop_Type', 'Date_Bought']].copy()
        df_display.rename(columns={'Date_Bought': 'Sub Category'}, inplace=True)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.write("You have no pending items!")
