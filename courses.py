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

# Fetch Course Data for the Library Dashboard
@st.cache_data(ttl=60)
def load_courses():
    try:
        course_sh = gc.open("COURSE_LOG")
        return pd.DataFrame(course_sh.sheet1.get_all_records())
    except Exception:
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

# ------------------------------------------
# SECTION 1: DATA ENTRY FORM
# ------------------------------------------
with st.expander("📝 Add New Course / Workshop", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        course_name = st.text_input("Course / Workshop Name", placeholder="e.g., AI Tools Workshop")
        course_type = st.radio("Purpose / Type", ["Personal", "School"])
    with c2:
        provider = st.text_input("Provider / Platform", placeholder="e.g., be10x")
        finance_type = st.radio("Finance Type", ["Paid", "Free"])

    # Payment Details Section
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
                account_opts = ["MB", "AXIS Bank", "A. Cash"] 
            account_sel = st.selectbox("Paid From Account", account_opts)
        with pc3:
            # Defaults to whatever is typed in the Provider box
            to_from = st.text_input("Paid To (TO_FROM)", value=provider, placeholder="e.g., be10x")
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
                
                # 1. Connect to the separate Google Sheet file: "COURSE_LOG"
                try:
                    course_sh = gc.open("COURSE_LOG")
                    course_ws = course_sh.sheet1
                    
                    if not course_ws.get_all_values():
                        course_ws.append_row(["Date_Logged", "Course_Name", "Provider", "Type", "Finance", "Cost_INR", "Account", "To_From", "Schedule", "Login_Details"])
                        
                except gspread.exceptions.SpreadsheetNotFound:
                    st.error("⚠️ Could not find 'COURSE_LOG'. Please make sure you created the file in Google Drive and shared it with your service account email!")
                    st.stop()
                
                # Add data to COURSE_LOG file
                course_ws.append_row([
                    date_logged, course_name, provider, course_type, finance_type, cost, account_sel, to_from, schedule_date, login_details
                ])
                
                # 2. AUTOMATICALLY sync with main "sk_money_location" (SMART MAPPING)
                if finance_type == "Paid" and cost > 0:
                    money_sh = gc.open("sk_money_location")
                    money_ws = money_sh.worksheet("MONEY_DATA")
                    
                    entity = "PERS" if course_type == "Personal" else "WORK"
                    
                    # Read the headers of your MONEY_DATA tab
                    raw_headers = money_ws.row_values(1)
                    clean_headers = [str(h).strip().upper() for h in raw_headers]
                    
                    money_row = [""] * len(raw_headers)
                    
                    def fill_col(possible_names, value):
                        for name in possible_names:
                            clean_name = name.strip().upper()
                            if clean_name in clean_headers:
                                money_row[clean_headers.index(clean_name)] = value
                                return 
                    
                    # Precisely mapping every single value based on column names
                    fill_col(["DATE"], date_logged)
                    fill_col(["TIME"], time_logged)
                    fill_col(["IN"], "")
                    fill_col(["OUT"], cost)
                    fill_col(["ACCOUNT"], account_sel)
                    fill_col(["FUND"], "Salary")
                    fill_col(["ENTITY"], entity)
                    fill_col(["CATEGORY"], "EDUCATION")
                    fill_col(["SUB CATEGORY", "SUB-CATEGORY", "SUBCATEGORY"], "Course/Workshop")
                    fill_col(["PARTICULARS"], course_name)
                    fill_col(["TO_FROM", "TO/FROM", "TO / FROM", "TO FROM"], to_from) 
                    fill_col(["LOCATION"], "HOME") 
                    fill_col(["REMARK", "REMARKS"], "Auto-logged Course Fee")
                    
                    # Append the perfectly mapped row
                    money_ws.append_row(money_row)
                    clear_money_cache.clear() 
                    
                    st.success(f"✅ Course saved to COURSE_LOG and ₹{cost} synced perfectly to main ledger!")
                else:
                    st.success("✅ Free course details saved to COURSE_LOG successfully!")
                
                # Refresh the course library dashboard instantly
                load_courses.clear()
                st.balloons()
            except Exception as e:
                st.error(f"Error saving data: {e}")
        else:
            st.warning("⚠️ Please provide at least the Course Name and Provider.")


# ------------------------------------------
# SECTION 2: MY COURSE LIBRARY DASHBOARD
# ------------------------------------------
st.divider()
st.subheader("📚 My Course Library")

df_courses = load_courses()

if df_courses.empty:
    st.info("No courses logged yet. Fill out the form above to add your first workshop!")
else:
    # Reverse the dataframe so the newest added courses appear at the top
    df_courses = df_courses.iloc[::-1].reset_index(drop=True)
    
    for index, row in df_courses.iterrows():
        # Handle cases where data might be missing safely
        c_name = row.get("Course_Name", "Unknown Course")
        c_prov = row.get("Provider", "Unknown Provider")
        
        # Create a beautiful expander title
        expander_title = f"{c_name} | 🏫 {c_prov}"
        
        with st.expander(expander_title):
            # Top row metrics
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Category", row.get("Type", "-"))
            
            finance = str(row.get("Finance", "-"))
            mc2.metric("Finance Type", finance)
            
            # Format the cost metric nicely
            cost_val = row.get("Cost_INR", 0)
            if finance.upper() == "FREE" or cost_val == 0 or cost_val == "":
                mc3.metric("Cost", "Free 🎉")
            else:
                mc3.metric("Cost", f"₹{cost_val}")
            
            # Additional details nicely formatted
            st.markdown(f"**🗓️ Schedule:** {row.get('Schedule', 'Not specified')}")
            
            # Show payment footprint if it was paid
            if finance.upper() == "PAID":
                st.caption(f"💳 *Paid from {row.get('Account', '-')} to {row.get('To_From', '-')} on {row.get('Date_Logged', '-')}*")
            
            # Login and Access details highlighted in a blue info box
            st.markdown("**🔑 Login & Access Details:**")
            access_info = str(row.get("Login_Details", "")).strip()
            if access_info:
                st.info(access_info)
            else:
                st.warning("No access details saved for this course.")
