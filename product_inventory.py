import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- SETUP ---
st.set_page_config(page_title="Product Inventory", page_icon="📦", layout="wide")

# --- BACK BUTTON (STRICTLY REQUIRED) ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py")
st.write("---") 
# ---------------------------------------

# --- MOBILE KEYBOARD FIX ---
st.markdown("""
    <style>
    div[data-baseweb="select"] input { pointer-events: none !important; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds).open("sk_money_location")

sh = init_connection()

# --- CACHE INVENTORY DATA ---
@st.cache_data(ttl=60)
def load_inventory():
    try: return pd.DataFrame(sh.worksheet("PRODUCT_INVENTORY").get_all_records())
    except: return pd.DataFrame()

df = load_inventory()

# --- FORM ---
with st.expander("➕ Add New Product", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Product Name")
        buy_date = st.date_input("Buying Date")
        mrp = st.number_input("MRP (₹)", min_value=0.0, step=1.0)
        buy_price = st.number_input("Buying Price (₹)", min_value=0.0, step=1.0)
        sch_per = st.selectbox("SCH / PER", ["PER", "SCH"])
    with col2:
        mfd = st.text_input("MFD (e.g., 10/25 or DD-MM-YY)")
        exp = st.text_input("EXP (e.g., 12/26 or DD-MM-YY)")
        
        existing_sizes = []
        if not df.empty and 'Size (ml/g)' in df.columns:
            existing_sizes = list(dict.fromkeys([str(s).strip() for s in df['Size (ml/g)'].dropna() if str(s).strip() != ""]))
        
        size_opts = existing_sizes + ["-- Type New --"]
        sel_size = st.selectbox("Size (ml/g)", size_opts)
        
        if sel_size == "-- Type New --":
            size = st.text_input("Type New Size (e.g. 500g / 1L)")
        else:
            size = sel_size
            
        qty = st.number_input("Quantity", min_value=1, value=1, step=1)
    
    if st.button("💾 Save Product", type="primary"):
        if p_name and size:
            sh.worksheet("PRODUCT_INVENTORY").append_row([
                p_name, buy_date.strftime("%d-%m-%Y"), mrp, buy_price, 
                mfd, exp, size, qty, sch_per, "Active", ""
            ])
            load_inventory.clear() 
            st.success("Product Added!")
            st.rerun()
        else: st.warning("Enter product name and size!")

# --- DISPLAY & FINISH LOGIC ---
st.write("---")
st.subheader("📦 Current Inventory")

if not df.empty:
    for idx, row in df.iterrows():
        if row.get('Status') == 'Active':
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1: 
                    st.write(f"**{row['Product Name']}** ({row.get('SCH / PER', '')})")
                    st.caption(f"Size: {row['Size (ml/g)']} | Qty: {row['Quantity']}")
                with c2: 
                    st.caption(f"MRP: ₹{row['MRP']} | Buy: ₹{row['Buying Price']} | Exp: {row['EXP']}")
                with c3:
                    if st.button("✅ Finish", key=f"fin_{idx}"):
                        ws = sh.worksheet("PRODUCT_INVENTORY")
                        ws.update_cell(idx + 2, 10, "Finished") 
                        ws.update_cell(idx + 2, 11, datetime.now().strftime("%d-%m-%Y")) 
                        load_inventory.clear() 
                        st.rerun()
else:
    st.info("No active products in inventory.")
