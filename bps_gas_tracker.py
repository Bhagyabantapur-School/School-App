import streamlit as st
import pandas as pd
from datetime import date

# Set page configuration
st.set_page_config(page_title="BPS Gas Tracker", page_icon="🔥", layout="centered")

# --- INITIALIZE SESSION STATE (Mock Database) ---
if 'gas_log' not in st.session_state:
    st.session_state.gas_log = pd.DataFrame(columns=[
        "Date", "Cylinder", "Action", "Cylinder Cost (₹)", "Delivery Cost (₹)", "Total Cost (₹)", "Ref/Notes"
    ])

if 'cyl_1_status' not in st.session_state:
    st.session_state.cyl_1_status = "In Use"

if 'cyl_2_status' not in st.session_state:
    st.session_state.cyl_2_status = "Empty"

# --- MAIN DASHBOARD ---
st.title("🔥 Bhagyabantapur Primary School - Gas Tracker")
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
    
    submitted = st.form_submit_button("Save Record")
    
    if submitted:
        # Update Status
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

        # Calculate total and append to Log DataFrame
        total_cost = cylinder_cost + delivery_cost
        
        new_record = pd.DataFrame([{
            "Date": action_date.strftime("%Y-%m-%d"),
            "Cylinder": target_cylinder,
            "Action": action_type,
            "Cylinder Cost (₹)": cylinder_cost,
            "Delivery Cost (₹)": delivery_cost,
            "Total Cost (₹)": total_cost,
            "Ref/Notes": notes
        }])
        
        st.session_state.gas_log = pd.concat([st.session_state.gas_log, new_record], ignore_index=True)
        
        # NOTE FOR GOOGLE SHEETS API: Update your append_row logic to match the 7 variables above.
        
        st.success(f"Successfully logged: {target_cylinder} marked as {action_type}. Total Cost: ₹{total_cost}")
        st.rerun()

st.divider()

# --- HISTORY & EXPENSES ---
st.subheader("📊 History & Expense Breakdown")

if not st.session_state.gas_log.empty:
    st.dataframe(st.session_state.gas_log, use_container_width=True, hide_index=True)
    
    # Calculate Expense Breakdown
    total_cyl = st.session_state.gas_log["Cylinder Cost (₹)"].sum()
    total_del = st.session_state.gas_log["Delivery Cost (₹)"].sum()
    grand_total = st.session_state.gas_log["Total Cost (₹)"].sum()
    
    col_met1, col_met2, col_met3 = st.columns(3)
    col_met1.metric(label="Total Cylinder Cost", value=f"₹ {total_cyl:,.2f}")
    col_met2.metric(label="Total Delivery Cost", value=f"₹ {total_del:,.2f}")
    col_met3.metric(label="Grand Total Expenses", value=f"₹ {grand_total:,.2f}")
else:
    st.info("No records found. Log an action above to start tracking.")
