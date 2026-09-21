import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# ==========================================
# ⚙️ CONFIGURATION & TIMEZONE
# ==========================================
st.set_page_config(page_title="CU Instruments Order", page_icon="🔬", layout="wide")
IST = pytz.timezone('Asia/Kolkata')

# ==========================================
# 🔐 SESSION STATE (Login Management)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = None

# ==========================================
# 🖥️ LOGIN SYSTEM
# ==========================================
def login_page():
    st.markdown("<h2 style='text-align: center; color: #002147;'>University of Calcutta</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>Instrument Booking Portal</h4>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        st.write("### Login")
        user_id = st.text_input("User ID (e.g., student1, admin)")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            # Note: In production, fetch this from the "Users" Google Sheet tab
            if user_id == "admin" and password == "admin123":
                st.session_state.logged_in = True
                st.session_state.user_role = "Admin"
                st.session_state.user_name = "System Admin"
                st.rerun()
            elif user_id == "student1" and password == "pass":
                st.session_state.logged_in = True
                st.session_state.user_role = "Student"
                st.session_state.user_name = "Rahul Sharma"
                st.rerun()
            else:
                st.error("Invalid Credentials")

# ==========================================
# 🎓 USER DASHBOARD (Students & Teachers)
# ==========================================
def user_dashboard():
    st.title(f"Welcome, {st.session_state.user_name} ({st.session_state.user_role})")
    
    tab1, tab2 = st.tabs(["📝 Book an Instrument", "🔔 My Notifications & Status"])
    
    with tab1:
        st.subheader("New Booking")
        # In production: Fetch these from the "Instruments" Google Sheet tab
        instruments = ["Electron Microscope (₹500/hr)", "Spectrophotometer (₹200/hr)", "Centrifuge (₹100/hr)"]
        slots = ["10:00 AM - 11:00 AM", "11:00 AM - 12:00 PM", "02:00 PM - 03:00 PM"]
        
        with st.form("booking_form"):
            selected_inst = st.selectbox("Select Instrument", instruments)
            date = st.date_input("Select Date")
            slot = st.selectbox("Select Time Slot", slots)
            book_btn = st.form_submit_button("Submit Booking Request")
            
            if book_btn:
                timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                # Write to Google Sheets "Bookings" tab here
                st.success(f"✅ Booking request sent! Your timestamp is {timestamp}. Check the Notifications tab for approval status.")

    with tab2:
        st.subheader("Booking Status (Live Updates)")
        # In production: Fetch filtered data from "Bookings" sheet where User Name == st.session_state.user_name
        mock_my_bookings = pd.DataFrame({
            "Date": ["2026-09-25", "2026-09-26"],
            "Instrument": ["Electron Microscope", "Centrifuge"],
            "Time Slot": ["10:00 AM - 11:00 AM", "02:00 PM - 03:00 PM"],
            "Payment Status": ["Pending", "Paid"],
            "Booking Status": ["⏳ Pending Admin Approval", "✅ Approved (Ready to Use)"]
        })
        st.dataframe(mock_my_bookings, use_container_width=True, hide_index=True)

# ==========================================
# ⚙️ ADMIN DASHBOARD
# ==========================================
def admin_dashboard():
    st.title("Admin Control Panel")
    
    tab1, tab2 = st.tabs(["🚦 Queue Management (Approve/Reject)", "🔬 Manage Instruments"])
    
    with tab1:
        st.subheader("Pending Booking Requests (Sorted by First-Come, First-Served)")
        
        # In production: Fetch from "Bookings" sheet and sort by Timestamp ascending
        mock_queue = pd.DataFrame({
            "Timestamp": ["2026-09-22 09:01:10", "2026-09-22 09:05:40", "2026-09-22 09:15:00"],
            "User": ["Rahul Sharma", "Priya Das", "Amit Roy"],
            "Instrument": ["Electron Microscope", "Electron Microscope", "Electron Microscope"],
            "Date": ["2026-09-25", "2026-09-25", "2026-09-25"],
            "Time Slot": ["10:00 AM - 11:00 AM", "10:00 AM - 11:00 AM", "10:00 AM - 11:00 AM"],
            "Payment Status": ["Pending", "Pending", "Pending"],
            "Booking Status": ["Pending", "Pending", "Pending"]
        })
        
        st.dataframe(mock_queue, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.write("**Action Panel: Process Next User in Queue**")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            target_user = st.selectbox("Select User to Update", mock_queue['User'].tolist())
        with col2:
            new_payment = st.selectbox("Payment Status", ["Pending", "Paid", "Failed"])
        with col3:
            new_status = st.selectbox("Booking Status", ["Pending", "Approved", "Rejected", "Completed"])
        with col4:
            st.write("")
            st.write("")
            if st.button("Update System", type="primary"):
                # In production: Find the row in Google Sheets and ws.update()
                st.success(f"Updated {target_user}: Payment -> {new_payment}, Status -> {new_status}")
                st.info("The user will now see this update in their login dashboard.")

    with tab2:
        st.subheader("Add/Edit Instruments")
        # Interface to append rows to the "Instruments" Google Sheet tab
        with st.form("add_instrument"):
            inst_name = st.text_input("Instrument Name")
            inst_price = st.number_input("Price Rate per hour (₹)", min_value=0)
            st.form_submit_button("Add to Database")

# ==========================================
# 🚀 APP ROUTING
# ==========================================
if not st.session_state.logged_in:
    login_page()
else:
    col1, col2 = st.columns([8, 1])
    with col2:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
            
    if st.session_state.user_role == "Admin":
        admin_dashboard()
    else:
        user_dashboard()
