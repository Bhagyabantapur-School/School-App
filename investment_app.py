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
st.set_page_config(page_title="Investment Tracker", page_icon="📈", layout="centered")

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

@st.cache_data(ttl=60)
def load_money_data():
    try: return pd.DataFrame(sh.worksheet("MONEY_DATA").get_all_records())
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
st.title("📈 Stock Market & Mutual Funds")
st.write("Track your SIPs, lumpsum buys, and portfolio cash flow.")

with st.expander("Log Investment Details", expanded=True):
    asset_opts = get_list("Investment_Assets")
    if not asset_opts:
        asset_opts = ["Mahindra Manulife Mutual Fund", "UTI Mutual Fund", "Index Fund", "Direct Equity", "-- Type New --"]
    elif "-- Type New --" not in asset_opts:
        asset_opts.append("-- Type New --")
        
    asset_sel = st.selectbox("Asset / Fund Name", asset_opts, key="inv_asset_sel")
    if asset_sel == "-- Type New --":
        asset_name = st.text_input("Type New Asset Name", key="inv_new_asset")
    else:
        asset_name = asset_sel

    inv_c1, inv_c2 = st.columns(2)
    with inv_c1:
        inv_type = st.selectbox("Transaction Type", [
            "Buy (SIP)", 
            "Buy (Lumpsum)", 
            "Sell (Redemption)", 
            "Dividend / Yield Payout"
        ], key="inv_type")
        inv_date = st.date_input("Transaction Date", value=st.session_state.locked_date, key="inv_date")
        
    with inv_c2:
        inv_amount = st.number_input("Total Amount (₹)", min_value=0.0, step=500.0, key="inv_amt")
        inv_units = st.number_input("Units / Qty (Optional)", min_value=0.0, step=0.001, format="%.3f", key="inv_units")

    # Optional: Calculate approximate NAV/Price if both amount and units are provided
    nav_calc = (inv_amount / inv_units) if inv_units > 0 else 0.0
    if nav_calc > 0:
        st.caption(f"🧮 *Calculated NAV/Price: ₹{nav_calc:.2f}*")

    if st.button("💾 Save & Sync Investment Log", use_container_width=True, type="primary"):
        if asset_name and inv_amount > 0:
            try:
                date_str = inv_date.strftime("%d-%m-%Y")
                time_str = get_ist_now().strftime("%H:%M")
                
                # 1. Log to the Portfolio Tracker
                try:
                    inv_ws = sh.worksheet("INVESTMENT_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    inv_ws = sh.add_worksheet(title="INVESTMENT_LOG", rows="100", cols="6")
                    inv_ws.append_row(["Date", "Asset_Name", "Transaction_Type", "Amount_INR", "Units_Qty", "NAV_or_Price"])
                
                inv_ws.append_row([
                    date_str, asset_name, inv_type, inv_amount, inv_units, round(nav_calc, 2)
                ])
                
                # 2. AUTOMATICALLY sync with Main MONEY_DATA
                # Because an SIP/Buy is a real cash deduction, and a Sell/Dividend is a real cash deposit.
                money_ws = sh.worksheet("MONEY_DATA")
                
                if "Buy" in inv_type:
                    # Money leaves MB (OUT), goes to ASSETS
                    money_row = [date_str, time_str, "", inv_amount, "MB", "Salary", "ASSETS", "INVESTMENT", "MUTUAL FUND / STOCK", asset_name, "", "", f"Auto-logged {inv_type}"]
                else:
                    # Money enters MB (IN), comes from ASSETS
                    money_row = [date_str, time_str, inv_amount, "", "MB", "", "ASSETS", "INCOME", "MARKET YIELD", asset_name, "", "", f"Auto-logged {inv_type}"]
                
                money_ws.append_row(money_row)
                load_money_data.clear() # Clear cache so main app updates
                
                st.success(f"✅ Logged {inv_type} for {asset_name} and synced with Main Money Ledger!")
                st.balloons()
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")
        else:
            st.warning("⚠️ Please provide the Asset Name and an Amount greater than zero.")
