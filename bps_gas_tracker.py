import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# 1. Set page configuration
st.set_page_config(page_title="BPS Gas Tracker", page_icon="🛢️", layout="centered")

# --- GOOGLE SHEETS CONNECTION (USING STREAMLIT SECRETS) ---
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
    )

@st.cache_resource
def init_connection():
    client = gspread.authorize(get_google_credentials())
    spreadsheet = client.open("BPS_Gas_Tracker")
    return spreadsheet.worksheet("Sheet1")

try:
    sheet = init_connection()
except Exception as e:
    st.error("⚠️ Could not connect to Google Sheets. Please check your Streamlit Secrets configuration and ensure you have shared 'BPS_Gas_Tracker' with your service account email as an Editor.")
    st.stop()

# --- LOAD DATA FROM SHEET ---
def load_data():
    records = sheet.get_all_records()
    if records:
        return pd.DataFrame(records)
    else:
        return pd.DataFrame(columns=[
            "Date", "Cylinder", "Action", "Cylinder Cost (₹)", "Delivery Cost (₹)", "Total Cost (₹)", "Ref/Notes"
        ])

# Fetch data into session state
if 'gas_log' not in st.session_state:
    st.session_state.gas_log = load_data()

# --- CALCULATE CURRENT CYLINDER STATUS ---
def get_latest_status(cylinder_name, default_status):
    df = st.session_state.gas_log
    if not df.empty:
        cyl_history = df[df["Cylinder"] == cylinder_name]
        if not cyl_history.empty:
            latest_action = cyl_history.iloc[-1]["Action"]
            if latest_action == "Booked": return "Booked"
            elif latest_action == "Received (Full)": return "Full (Standby)"
            elif latest_action == "Put in Use": return "In Use"
            elif latest_action == "Emptied": return "Empty"
    return default_status

st.session_state.cyl_1_status = get_latest_status("Cylinder 1", "In Use")
st.session_state.cyl_2_status = get_latest_status("Cylinder 2", "Empty")

# --- MAIN DASHBOARD ---
st.title("🛢️ Bhagyabantapur Primary School - Gas Tracker")
st.markdown("Track bookings, deliveries, and itemized costs for the school's cylinders.")

st.divider()

# Cylinder Status Cards
col1, col2 = st.columns(2)

with col1:
    st.subheader("Cylinder 1")
    if st.session_state.cyl_1_status == "In Use":
        st.success(f"Status: {st.session_state.cyl_1_status}")
    elif st.session_state.cyl_1_status == "Empty":
        st.error(f"Status: {st.session_state.cyl_1_status}")
    elif st.session_state.cyl_1_status == "Booked":
        st.warning(f"Status: {st.session_state.cyl_1_status}")
    else:
        st.info(f"Status: {st.session_state.cyl_1_status}")

with col2:
    st.subheader("Cylinder 2")
    if st.session_state.cyl_2_status == "In Use":
        st.success(f"Status: {st.session_state.cyl_2_status}")
    elif st.session_state.cyl_2_status == "Empty":
        st.error(f"Status: {st.session_state.cyl_2_status}")
    elif st.session_state.cyl_2_status == "Booked":
        st.warning(f"Status: {st.session_state.cyl_2_status}")
    else:
        st.info(f"Status: {st.session_state.cyl_2_status}")

st.divider()

# --- ACTION FORM ---
st.subheader("📝 Log an Action")

with st.form("gas_action_form"):
    action_date = st.date_input("Date", date.today())
    
    col_a, col_b = st.columns(2)
    with col_a:
        target_cylinder = st.selectbox("Select Cylinder", ["Cylinder 1", "Cylinder 2"])
    with col_b:
        action_type = st.selectbox("Action", ["Booked", "Received (Full)", "Put in Use", "Emptied"])
        
    st.markdown("**Expenses (Fill if booking or receiving)**")
    col_cost1, col_cost2 = st.columns(2)
    with col_cost1:
        cylinder_cost = st.number_input("Cylinder Cost (₹)", min_value=0.0, value=0.0, step=10.0)
    with col_cost2:
        delivery_cost = st.number_input("Delivery Cost (₹)", min_value=0.0, value=0.0, step=10.0)
        
    notes = st.text_input("Booking Ref No. / Notes")
    
    submitted = st.form_submit_button("Save Record to Google Sheets")
    
    if submitted:
        # Calculate total
        total_cost = cylinder_cost + delivery_cost
        date_str = action_date.strftime("%Y-%m-%d")
        
        # Prepare row matching the 7 columns in your sheet
        new_row = [
            date_str, 
            target_cylinder, 
            action_type, 
            cylinder_cost, 
            delivery_cost, 
            total_cost, 
            notes
        ]
        
        # Append to Google Sheets
        sheet.append_row(new_row)
        
        # Clear the cached session state so it pulls fresh data on reload
        del st.session_state.gas_log 
        
        st.success(f"Successfully saved to Google Sheets! {target_cylinder} marked as {action_type}.")
        st.rerun()

st.divider()

# --- HISTORY & EXPENSES ---
st.subheader("📊 History & Expense Breakdown")

if not st.session_state.gas_log.empty:
    st.dataframe(st.session_state.gas_log, use_container_width=True, hide_index=True)
    
    # Clean numeric columns in case Google Sheets brings in empty cells as strings
    df_calc = st.session_state.gas_log.copy()
    df_calc["Cylinder Cost (₹)"] = pd.to_numeric(df_calc["Cylinder Cost (₹)"], errors='coerce').fillna(0)
    df_calc["Delivery Cost (₹)"] = pd.to_numeric(df_calc["Delivery Cost (₹)"], errors='coerce').fillna(0)
    df_calc["Total Cost (₹)"] = pd.to_numeric(df_calc["Total Cost (₹)"], errors='coerce').fillna(0)
    
    # Calculate Expense Breakdown
    total_cyl = df_calc["Cylinder Cost (₹)"].sum()
    total_del = df_calc["Delivery Cost (₹)"].sum()
    grand_total = df_calc["Total Cost (₹)"].sum()
    
    col_met1, col_met2, col_met3 = st.columns(3)
    col_met1.metric(label="Total Cylinder Cost", value=f"₹ {total_cyl:,.2f}")
    col_met2.metric(label="Total Delivery Cost", value=f"₹ {total_del:,.2f}")
    col_met3.metric(label="Grand Total Expenses", value=f"₹ {grand_total:,.2f}")
else:
    st.info("No records found in Google Sheets. Log an action above to start tracking.")
