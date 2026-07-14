import streamlit as st
import pandas as pd
from datetime import date

# Set page configuration
st.set_page_config(page_title="School Gas Tracker", page_icon="🔥", layout="centered")

# --- INITIALIZE SESSION STATE (Mock Database) ---
# In a production environment, you would pull this initial data from your Google Sheet
if 'gas_log' not in st.session_state:
    st.session_state.gas_log = pd.DataFrame(columns=["Date", "Cylinder", "Action", "Cost (₹)", "Ref/Notes"])

if 'cyl_1_status' not in st.session_state:
    st.session_state.cyl_1_status = "In Use"

if 'cyl_2_status' not in st.session_state:
    st.session_state.cyl_2_status = "Empty"

# --- MAIN DASHBOARD ---
st.title("🔥 School Gas Management")
st.markdown("Track bookings, deliveries, and daily usage for the school's two cylinders.")

st.divider()

# Cylinder Status Cards
col1, col2 = st.columns(2)

with col1:
    st.subheader("Cylinder 1")
    # Color coding based on status
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
        
    expense = st.number_input("Cost / Expense (₹) - if booking/receiving", min_value=0.0, value=0.0, step=50.0)
    notes = st.text_input("Booking Ref No. / Notes")
    
    submitted = st.form_submit_button("Save Record")
    
    if submitted:
        # 1. Update the Current Status of the selected cylinder
        new_status = ""
        if action_type == "Booked":
            new_status = "Booked"
        elif action_type == "Received (Full)":
            new_status = "Full (Standby)"
        elif action_type == "Put in Use":
            new_status = "In Use"
        elif action_type == "Emptied":
            new_status = "Empty"

        if target_cylinder == "Cylinder 1":
            st.session_state.cyl_1_status = new_status
        else:
            st.session_state.cyl_2_status = new_status

        # 2. Append to the Log DataFrame
        new_record = pd.DataFrame([{
            "Date": action_date.strftime("%Y-%m-%d"),
            "Cylinder": target_cylinder,
            "Action": action_type,
            "Cost (₹)": expense,
            "Ref/Notes": notes
        }])
        
        st.session_state.gas_log = pd.concat([st.session_state.gas_log, new_record], ignore_index=True)
        
        # NOTE FOR INTEGRATION: 
        # This is where you would call your Google Sheets append_row() function.
        # Example: sheet.append_row([str(action_date), target_cylinder, action_type, expense, notes])
        
        st.success(f"Successfully logged: {target_cylinder} marked as {action_type}.")
        st.rerun()

st.divider()

# --- HISTORY & EXPENSES ---
st.subheader("📊 History & Expenses Tracker")

# Display the dataframe
if not st.session_state.gas_log.empty:
    st.dataframe(st.session_state.gas_log, use_container_width=True, hide_index=True)
    
    # Calculate Total Expenses
    total_expense = st.session_state.gas_log["Cost (₹)"].sum()
    st.metric(label="Total Gas Expenses", value=f"₹ {total_expense:,.2f}")
else:
    st.info("No records found. Log an action above to start tracking.")
