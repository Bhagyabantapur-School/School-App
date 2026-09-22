import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
import time

# ==========================================
# ⚙️ CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="CU IMS", page_icon="🔬", layout="wide")
IST = pytz.timezone('Asia/Kolkata')

SHEET_NAME = "CU Instruments Order"

# ==========================================
# 🧠 SESSION STATE
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = None

# ==========================================
# 🔌 GOOGLE SHEETS CONNECTOR & AUTO-SETUP
# ==========================================
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
def init_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open(SHEET_NAME)
    except Exception as e: 
        st.error(f"⚠️ Connection Error: {e}")
        st.stop()

@st.cache_resource
def setup_database():
    """Automatically creates necessary tabs and headers in Google Sheets"""
    sh = init_sheet()
    
    # 1. Instruments Tab
    try:
        ws_inst = sh.worksheet("Instruments")
    except WorksheetNotFound:
        ws_inst = sh.add_worksheet(title="Instruments", rows="100", cols="20")
    
    if not ws_inst.get_all_values():
        ws_inst.append_row(['Instrument ID', 'Name', 'Price Rate (₹)', 'Available Slots', 'Status'])

    # 2. Bookings Tab
    try:
        ws_book = sh.worksheet("Bookings")
    except WorksheetNotFound:
        ws_book = sh.add_worksheet(title="Bookings", rows="1000", cols="20")
        
    if not ws_book.get_all_values():
        ws_book.append_row(['Booking ID', 'Timestamp', 'User Name', 'Role', 'Instrument', 'Date', 'Time Slot', 'Payment Status', 'Booking Status'])

    # 3. Users Tab
    try:
        ws_users = sh.worksheet("Users")
    except WorksheetNotFound:
        ws_users = sh.add_worksheet(title="Users", rows="100", cols="20")
        
    users_data = ws_users.get_all_values()
    if not users_data:
        ws_users.append_row(['User ID', 'Password', 'Role'])
        # 🔑 Auto-inject default accounts
        ws_users.append_row(['admin', 'admin123', 'Admin'])
        ws_users.append_row(['student1', 'pass123', 'Student'])
        
    return sh

# 🚀 Run the Auto-Setup silently
sh = setup_database()

# --- HELPER FUNCTION TO PREVENT KEYERRORS ---
def get_clean_dataframe(sheet_tab_name):
    """Safely fetches data from Google Sheet and strips any accidental spaces from headers"""
    try:
        ws = sh.worksheet(sheet_tab_name)
        raw_data = ws.get_all_values()
        if len(raw_data) > 1:
            # Strip spaces from headers
            df = pd.DataFrame(raw_data[1:], columns=[str(c).strip() for c in raw_data[0]])
            return df
        elif len(raw_data) == 1:
            # Only headers exist, return empty dataframe with proper columns
            return pd.DataFrame(columns=[str(c).strip() for c in raw_data[0]])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ Error fetching from '{sheet_tab_name}' tab: {e}")
        return pd.DataFrame()

# ==========================================
# 🖥️ LOGIN SYSTEM
# ==========================================
def login_page():
    st.markdown("<h2 style='text-align: center; color: #002147;'>University of Calcutta</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>Instrument Booking & Priority Portal</h4>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        st.write("### Login")
        user_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            users_df = get_clean_dataframe("Users")
            
            # 1. Check if headers are correct
            if 'User ID' in users_df.columns and 'Password' in users_df.columns:
                
                # 2. Check if the sheet is empty
                if not users_df.empty:
                    users_df['User ID'] = users_df['User ID'].astype(str).str.strip()
                    users_df['Password'] = users_df['Password'].astype(str).str.strip()
                    
                    user_match = users_df[(users_df['User ID'] == str(user_id).strip()) & (users_df['Password'] == str(password).strip())]
                    
                    if not user_match.empty:
                        st.session_state.logged_in = True
                        st.session_state.user_role = user_match.iloc[0]['Role']
                        st.session_state.user_name = user_id
                        st.rerun()
                    else:
                        st.error("🚨 Invalid User ID or Password")
                else:
                    st.error("⚠️ No users found! Please log into the Google Sheet's 'Users' tab and add at least one Admin account.")
            else:
                st.error("⚠️ Database Setup Error: The headers in the 'Users' tab (Row 1) must be 'User ID', 'Password', and 'Role'.")

# ==========================================
# 🎓 USER DASHBOARD
# ==========================================
def user_dashboard():
    st.title(f"Welcome, {st.session_state.user_name} ({st.session_state.user_role})")
    
    tab1, tab2 = st.tabs(["📝 Book an Instrument", "🔔 My Notifications & Status"])
    
    with tab1:
        st.subheader("New Booking Request")
        
        inst_df = get_clean_dataframe("Instruments")
        
        if inst_df.empty or 'Name' not in inst_df.columns:
            st.info("No instruments are currently available. Admin needs to add them first.")
        else:
            inst_list = inst_df['Name'].tolist()
            slots = ["10:00 AM - 11:00 AM", "11:00 AM - 12:00 PM", "02:00 PM - 03:00 PM", "03:00 PM - 04:00 PM"]
            
            with st.form("booking_form"):
                selected_inst = st.selectbox("Select Instrument", inst_list)
                date = st.date_input("Select Date")
                slot = st.selectbox("Select Time Slot", slots)
                book_btn = st.form_submit_button("Submit Booking Request")
                
                if book_btn:
                    ws_book = sh.worksheet("Bookings")
                    booking_id = f"BKG-{int(datetime.now(IST).timestamp())}"
                    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    
                    row_data = [booking_id, timestamp, st.session_state.user_name, st.session_state.user_role, selected_inst, str(date), slot, "Pending", "Pending"]
                    ws_book.append_row(row_data)
                    
                    st.success(f"✅ Booking request sent! Your precise timestamp is **{timestamp}**. Priority is strictly First-Come, First-Served.")

    with tab2:
        st.subheader("Booking Status (Live Updates)")
        all_bookings = get_clean_dataframe("Bookings")
        
        if not all_bookings.empty and 'User Name' in all_bookings.columns:
            my_bookings = all_bookings[all_bookings['User Name'] == st.session_state.user_name]
            if not my_bookings.empty:
                st.dataframe(my_bookings[['Date', 'Time Slot', 'Instrument', 'Payment Status', 'Booking Status']], use_container_width=True, hide_index=True)
            else:
                st.info("You have no booking history.")
        else:
            st.info("You have no booking history.")

# ==========================================
# ⚙️ ADMIN DASHBOARD
# ==========================================
def admin_dashboard():
    st.title("Admin Control Panel")
    
    tab1, tab2, tab3 = st.tabs(["🚦 Queue Management (FCFS)", "🔬 Manage Instruments", "👥 Manage Users"])
    
    with tab1:
        st.subheader("Booking Queue")
        
        bookings_df = get_clean_dataframe("Bookings")
        
        if not bookings_df.empty:
            # 🛡️ SAFETY NET: Verify all required columns exist before processing
            required_cols = ['Booking ID', 'Timestamp', 'Date', 'Time Slot']
            missing_cols = [col for col in required_cols if col not in bookings_df.columns]
            
            if missing_cols:
                st.error(f"⚠️ **Google Sheet Header Error:** The 'Bookings' tab is missing the following exact headers: **{', '.join(missing_cols)}**.")
                st.info("💡 Please open your Google Sheet, go to the 'Bookings' tab, and ensure Row 1 has the exact headers spelled correctly without extra spaces.")
            else:
                # Sort by Date, Time Slot, and exact Timestamp
                bookings_df = bookings_df.sort_values(by=['Date', 'Time Slot', 'Timestamp'])
                
                st.dataframe(bookings_df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.write("**Process Next User in Queue**")
                
                with st.form("update_booking"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        target_bkg = st.selectbox("Select Booking ID", bookings_df['Booking ID'].tolist())
                    with col2:
                        new_payment = st.selectbox("Payment Status", ["Pending", "Paid", "Failed/Refunded"])
                    with col3:
                        new_status = st.selectbox("Booking Status", ["Pending", "Approved", "Waitlisted", "Rejected", "Completed"])
                    
                    if st.form_submit_button("Update System", type="primary"):
                        ws_book = sh.worksheet("Bookings")
                        live_values = ws_book.get_all_values()
                        
                        row_to_update = None
                        for i, row in enumerate(live_values):
                            if i > 0 and str(row[0]).strip() == str(target_bkg).strip():
                                row_to_update = i + 1 
                                break
                        
                        if row_to_update:
                            ws_book.update(values=[[new_payment, new_status]], range_name=f"H{row_to_update}:I{row_to_update}")
                            st.success(f"✅ Booking {target_bkg} updated successfully. User will see this in their portal.")
                            get_clean_dataframe.clear()
                            st.rerun()
        else:
            st.info("No bookings currently in the system.")

    with tab2:
        st.subheader("Add New Instrument")
        with st.form("add_instrument"):
            inst_id = st.text_input("Instrument ID (e.g., INST-01)")
            inst_name = st.text_input("Instrument Name")
            inst_price = st.number_input("Price Rate per hour (₹)", min_value=0)
            
            if st.form_submit_button("Add to Database"):
                if inst_id and inst_name:
                    ws_inst = sh.worksheet("Instruments")
                    ws_inst.append_row([inst_id, inst_name, inst_price, "Open", "Active"])
                    st.success(f"✅ {inst_name} added to the database.")
                    get_clean_dataframe.clear()
                else:
                    st.error("Please provide both Instrument ID and Name.")

    # 👥 "Manage Users" Functionality
    with tab3:
        st.subheader("Current System Users")
        users_df = get_clean_dataframe("Users")
        
        if not users_df.empty:
            # Hide passwords from display
            display_users = users_df.copy()
            if 'Password' in display_users.columns:
                display_users['Password'] = '******'
            st.dataframe(display_users, use_container_width=True, hide_index=True)
        else:
            st.info("No users found in the system.")
            
        st.markdown("---")
        st.subheader("➕ Add New User")
        st.info("💡 **Note:** Users added here are immediately active.")
        
        with st.form("add_new_user"):
            new_uid = st.text_input("New User ID (e.g., prof_amit)")
            new_pass = st.text_input("Temporary Password")
            new_role = st.selectbox("Select Role", ["Student", "Teacher", "Admin"])
            submit_user = st.form_submit_button("Add User to System", type="primary")
            
            if submit_user:
                if not new_uid or not new_pass:
                    st.error("🚨 Both User ID and Password are required.")
                elif len(new_uid.strip()) < 3 or len(new_pass.strip()) < 4:
                    st.error("🚨 User ID must be at least 3 characters and Password at least 4 characters.")
                else:
                    ws_users = sh.worksheet("Users")
                    existing_users = pd.DataFrame(ws_users.get_all_records())
                    
                    # Prevent Duplicate Users
                    if not existing_users.empty and str(new_uid).strip() in existing_users['User ID'].astype(str).str.strip().tolist():
                        st.error(f"🚨 The User ID '{new_uid}' already exists. Please choose a different ID.")
                    else:
                        with st.spinner("Adding user to secure database..."):
                            try:
                                # Append Row: ID, Password, Role
                                ws_users.append_row([new_uid.strip(), new_pass.strip(), new_role])
                                st.success(f"🎉 Account for **{new_uid}** ({new_role}) created successfully!")
                                get_clean_dataframe.clear()
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Error saving to Google Sheet: {e}")

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
