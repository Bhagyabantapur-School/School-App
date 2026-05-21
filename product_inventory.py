import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- SETUP ---
st.set_page_config(page_title="Product Inventory", page_icon="📦", layout="wide")

# Back to Hub
if st.button("⬅️ Back to Hub"): st.switch_page("routine_audit.py")

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds).open("sk_money_location")

sh = init_connection()

# --- FORM ---
with st.expander("➕ Add New Product", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Product Name")
        buy_date = st.date_input("Buying Date")
        mrp = st.number_input("MRP (₹)", step=1.0)
        buy_price = st.number_input("Buying Price (₹)", step=1.0)
        sch_per = st.selectbox("SCH / PER", ["Perishable", "Non-Perishable"])
    with col2:
        mfd = st.date_input("MFD")
        exp = st.date_input("EXP")
        size = st.text_input("Size (e.g. 500g / 1L)") # Changed to text for flexibility
        qty = st.number_input("Quantity", step=1)
    
    if st.button("💾 Save Product", type="primary"):
        if p_name:
            # Note: 11 columns total now
            sh.worksheet("PRODUCT_INVENTORY").append_row([
                p_name, buy_date.strftime("%d-%m-%Y"), mrp, buy_price, 
                mfd.strftime("%d-%m-%Y"), exp.strftime("%d-%m-%Y"), size, qty, sch_per, "Active", ""
            ])
            st.success("Product Added!")
            st.rerun()
        else: st.warning("Enter product name!")

# --- DISPLAY & FINISH LOGIC ---
st.write("---")
st.subheader("📦 Current Inventory")
raw_data = sh.worksheet("PRODUCT_INVENTORY").get_all_records()
df = pd.DataFrame(raw_data)

if not df.empty:
    for idx, row in df.iterrows():
        if row['Status'] == 'Active':
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1: 
                    st.write(f"**{row['Product Name']}** ({row['SCH / PER']})")
                    st.caption(f"Size: {row['Size (ml/g)']} | Qty: {row['Quantity']}")
                with c2: 
                    st.caption(f"MRP: ₹{row['MRP']} | Buy: ₹{row['Buying Price']} | Exp: {row['EXP']}")
                with c3:
                    if st.button("✅ Finish", key=f"fin_{idx}"):
                        ws = sh.worksheet("PRODUCT_INVENTORY")
                        # Adjusting indices for new column layout
                        ws.update_cell(idx + 2, 10, "Finished") # Status
                        ws.update_cell(idx + 2, 11, datetime.now().strftime("%d-%m-%Y")) # Finish Date
                        st.rerun()
else:
    st.info("No active products in inventory.")
