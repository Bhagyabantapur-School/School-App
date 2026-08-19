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
st.set_page_config(page_title="Affiliate Tracker", page_icon="🛒", layout="centered")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

if 'locked_date' not in st.session_state: 
    st.session_state.locked_date = get_ist_now().date()

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

config_df = load_config()

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

# ==========================================
# APP LAYOUT
# ==========================================
st.title("🛒 Affiliate Sales & Commissions")
st.write("Track your links, clicks, conversions, and estimated commissions.")

with st.expander("Log Affiliate Performance", expanded=True):
    aff_opts = get_list("Affiliate_Programs")
    if not aff_opts: aff_opts = ["Amazon Associates", "Flipkart Affiliate", "Hostinger", "-- Type New --"]
    if "-- Type New --" not in aff_opts: aff_opts.append("-- Type New --")
        
    aff_prog_sel = st.selectbox("Select Affiliate Program", aff_opts, key="aff_prog")
    aff_program = st.text_input("Type New Program Name") if aff_prog_sel == "-- Type New --" else aff_prog_sel

    aff_product = st.text_input("Product or Campaign Promoted (e.g., DJI Mic Mini)")
    
    aff_c1, aff_c2, aff_c3 = st.columns(3)
    with aff_c1: aff_date = st.date_input("Date", value=st.session_state.locked_date, key="aff_date")
    with aff_c2: aff_clicks = st.number_input("Link Clicks", min_value=0, step=10, key="aff_clicks")
    with aff_c3: aff_conversions = st.number_input("Conversions (Sales)", min_value=0, step=1, key="aff_conv")
        
    aff_commission = st.number_input("Estimated Commission Earned (₹)", min_value=0.0, step=50.0, key="aff_comm")

    if st.button("💾 Save Affiliate Log", use_container_width=True, type="primary"):
        if aff_program and aff_product:
            try:
                date_str = aff_date.strftime("%d-%m-%Y")
                try: aff_ws = sh.worksheet("AFFILIATE_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    aff_ws = sh.add_worksheet(title="AFFILIATE_LOG", rows="100", cols="6")
                    aff_ws.append_row(["Date", "Program", "Product_or_Campaign", "Clicks", "Conversions", "Estimated_Commission"])
                
                aff_ws.append_row([date_str, aff_program, aff_product, aff_clicks, aff_conversions, aff_commission])
                st.success(f"✅ Logged {aff_conversions} sales for {aff_program}!")
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide both the Program and the Product name.")
