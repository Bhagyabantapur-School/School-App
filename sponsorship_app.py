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
st.set_page_config(page_title="Sponsorship Tracker", page_icon="🤝", layout="centered")

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
st.title("🤝 Sponsorship & Brand Deals")
st.write("Track your brand deals, deliverables, and payment statuses.")

with st.expander("Log Sponsorship Details", expanded=True):
    sponsor_opts = get_list("Sponsors")
    if not sponsor_opts: sponsor_opts = ["-- Type New --"]
    elif "-- Type New --" not in sponsor_opts: sponsor_opts.append("-- Type New --")
        
    sp_brand_sel = st.selectbox("Sponsor / Brand Name", sponsor_opts, key="sp_brand_sel")
    sp_brand = st.text_input("Type New Brand Name", key="sp_new_brand") if sp_brand_sel == "-- Type New --" else sp_brand_sel

    sp_campaign = st.text_input("Campaign or Video Title")
    
    sp_c1, sp_c2 = st.columns(2)
    with sp_c1:
        sp_type = st.selectbox("Deliverable Type", ["Integrated (60-90s)", "Dedicated Video", "YouTube Shorts", "Community Post", "Bundle"])
        sp_status = st.selectbox("Current Status", ["Pitching / Outreach", "Negotiating", "Contract Signed", "Content Submitted for Approval", "Content Live", "Invoice Sent", "✅ Paid"])
    
    with sp_c2:
        sp_publish_date = st.date_input("Target Publish Date", value=st.session_state.locked_date, key="sp_pub_date")
        sp_fee = st.number_input("Agreed Fee (₹)", min_value=0.0, step=1000.0, key="sp_fee")

    if st.button("💾 Save Sponsorship Log", use_container_width=True, type="primary"):
        if sp_brand and sp_campaign:
            try:
                today_str = get_ist_now().strftime("%d-%m-%Y")
                publish_str = sp_publish_date.strftime("%d-%m-%Y")
                
                try: sp_ws = sh.worksheet("SPONSORSHIP_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    sp_ws = sh.add_worksheet(title="SPONSORSHIP_LOG", rows="100", cols="7")
                    sp_ws.append_row(["Date_Logged", "Brand_Name", "Campaign_or_Video", "Deliverable_Type", "Status", "Target_Publish_Date", "Agreed_Fee"])
                
                sp_ws.append_row([today_str, sp_brand, sp_campaign, sp_type, sp_status, publish_str, sp_fee])
                st.success(f"✅ Logged deal with {sp_brand} as '{sp_status}'!")
                if sp_status == "✅ Paid": st.info("Remember to log the actual cash received in the main Money app!")
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide the Brand Name and Campaign Title.")
