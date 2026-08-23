import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="Course & Learning Tracker", page_icon="🎓", layout="centered")

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    return gc

try:
    gc = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google APIs. Error: {e}")
    st.stop()

# Fetch Config Data for the Accounts Dropdown
@st.cache_data(ttl=600)
def load_config():
    try:
        money_sh = gc.open("sk_money_location")
        return pd.DataFrame(money_sh.worksheet("CONFIG").get_all_records())
    except Exception as e:
        return pd.DataFrame()

config_df = load_config()

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

@st.cache_data(ttl=60)
def clear_money_cache():
    return True

# ==========================================
# APP LAYOUT
# ==========================================
st.title("🎓 Course & Learning Tracker")
st.write("Track your workshops and automatically sync payments to your main ledger.")

with st.expander("📝 Add New Course / Workshop", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        course_name = st.text_input("Course / Workshop Name", placeholder="e.g., AI Tools Workshop")
        course_type = st.radio("Purpose / Type", ["Personal", "School"])
    with c2:
        provider = st.text_input("Provider / Platform", placeholder="e.g., be10x")
        finance_type = st.radio("Finance Type", ["Paid", "Free"])

    # Payment Details Section (Only shows if Paid is selected)
    cost = 0.0
    account_sel = ""
    to_from = ""
    
    if finance_type == "Paid":
        st.divider()
        st.caption("💳 **Payment Details (Syncs to sk_money_location)**")
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            cost = st.number_input("Course Fee (₹)", min_value=0.0, step=50.0, format="%.2f")
        with pc2:
            account_opts = get_list("Account")
            if not account_opts: 
                account_opts = ["MB", "AXIS Bank", "A. Cash"] # Fallback if config is empty
            account_sel = st.selectbox("Paid From Account", account_opts)
        with pc3:
            # Defaults to whatever is typed in the Provider box to save you time!
            to_from = st.text_input("Paid To (TO / FROM)", value=provider, placeholder="e.g., be10x")
        st.divider()

    schedule_date = st.text_input("Schedule Date & Time", placeholder="e.g., 30-Aug-2026 11:00 AM")
    
    login_details = st.text_area(
        "Login / Access Details", 
        placeholder="e.g., Downloaded Android app be10x, joined WhatsApp group..."
    )

    if st.button("💾 Save Course Data", use_container_width=True, type="primary"):
        if course_name and provider:
            try:
                date_logged = get_ist_now().strftime("%d-%m-%Y")
                time_logged = get_ist_now().strftime("%H:%M")
                
                # 1. Connect to the NEW separate Google Sheet file: "COURSE_LOG"
                try:
                    course_sh = gc.open("COURSE_LOG")
                    course_ws = course_sh.sheet1
                    
                    if not course_ws.get_all_values():
                        # Expanded headers to include the new payment data
                        course_ws.append_row(["Date_Logged", "Course_Name", "Provider", "Type", "Finance", "Cost_INR", "Account", "To_From", "Schedule", "Login_Details"])
                        
                except gspread.exceptions.SpreadsheetNotFound:
                    st.error("⚠️ Could not find 'COURSE_LOG'. Please make sure you created the file in Google Drive and shared it with your service account email!")
                    st.stop()
                
                # Add data to COURSE_LOG file
                course_ws.append_row([
                    date_logged, course_name, provider, course_type, finance_type, cost, account_sel, to_from, schedule_date, login_details
                ])
                
                # 2. AUTOMATICALLY sync with main "sk_money_location" if it is Paid
                if finance_type == "Paid" and cost > 0:
                    money_sh = gc.open("sk_money_location")
                    money_ws = money_sh.worksheet("MONEY_DATA")
                    
                    entity = "PERS" if course_type == "Personal" else "WORK"
                    
                    # Uses your dynamically selected Account and To_From values
                    money_row = [
                        date_logged, time_logged, "", cost, account_sel, "Salary", 
                        entity, "EDUCATION", "Course/Workshop", course_name, "", to_from, "Auto-logged Course Fee"
                    ]
                    
                    money_ws.append_row(money_row)
                    clear_money_cache.clear() 
                    
                    st.success(f"✅ Course saved to COURSE_LOG and ₹{cost} synced from {account_sel} to main ledger!")
                else:
                    st.success("✅ Free course details saved to COURSE_LOG successfully!")
                    
                st.balloons()
            except Exception as e:
                st.error(f"Error saving data: {e}")
        else:
            st.warning("⚠️ Please provide at least the Course Name and Provider.")
