import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
import time
import hashlib

# ==========================================
# ⚙️ CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="CU IMS", page_icon="🔬", layout="wide")
IST = pytz.timezone('Asia/Kolkata')

SHEET_NAME = "CU Instruments Order"

# Role Definitions
CU_USERS = ["Faculty", "Research Scholar"]
NON_CU_USERS = ["Research Institute", "Industry partner"]
STAFF_USERS = ["Instrument Incharge"]
ALL_ROLES = ["Admin"] + CU_USERS + NON_CU_USERS + STAFF_USERS

# ==========================================
# 🎨 CUSTOM BUTTON CSS
# ==========================================
st.markdown("""
<style>
/* 🔴 Logout Button Styling */
div.element-container:has(#logout_marker) + div.element-container button {
    background-color: #dc3545 !important;
    color: white !important;
    border-color: #dc3545 !important;
    font-weight: bold !important;
}
div.element-container:has(#logout_marker) + div.element-container button:hover {
    background-color: #c82333 !important;
    border-color: #bd2130 !important;
    color: white !important;
}

/* 🔵 Sync Button Styling */
div.element-container:has(#sync_marker) + div.element-container button {
    background-color: #007bff !important;
    color: white !important;
    border-color: #007bff !important;
    font-weight: bold !important;
}
div.element-container:has(#sync_marker) + div.element-container button:hover {
    background-color: #0069d9 !important;
    border-color: #0062cc !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔒 SECURITY HELPER
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================
# 🎨 TABLE STYLING HELPERS
# ==========================================
def highlight_rows(row):
    """Applies CSS background colors to a pandas row based on Booking Status."""
    status = str(row.get('Booking Status', '')).strip()
    
    if status in ['Instrument Assigned', 'Completed']:
        color = '#d4edda' # Light Green
    elif status == 'Expired':
        color = '#b2babb' # Ash Gray
    elif status in ['Rejected', 'Rejected by Faculty']:
        color = '#f8d7da' # Light Red
    elif status == 'Approved, Awaiting Payment':
        color = '#cce5ff' # Light Blue
    elif status == 'Payment Submitted, Awaiting Verification':
        color = '#ffe8a1' # Light Gold/Orange
    elif status == 'Awaiting Faculty Recommendation':
        color = '#e8daef' # Light Purple
    elif status == 'Pending Admin Approval':
        color = '#fff3cd' # Light Yellow
    elif status == 'Waitlisted':
        color = '#e2e3e5' # Light Gray
    else:
        color = '' 
        
    if color:
        return [f'background-color: {color}; color: #000000'] * len(row)
    return [''] * len(row)

def highlight_instruments(row):
    """Applies CSS background colors to Instruments based on Working condition."""
    status = str(row.get('Status', '')).strip()
    
    if status == 'Not Working':
        color = '#f8d7da' # Light Red
    else:
        color = '' 
        
    if color:
        return [f'background-color: {color}; color: #000000'] * len(row)
    return [''] * len(row)

# ==========================================
# 🧠 SESSION STATE
# ==========================================
for state in ['logged_in', 'user_role', 'user_name', 'user_category']:
    if state not in st.session_state:
        st.session_state[state] = False if state == 'logged_in' else None

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

def setup_database():
    sh = init_sheet()
    
    try: sh.worksheet("Instruments")
    except WorksheetNotFound: 
        ws_inst = sh.add_worksheet(title="Instruments", rows="100", cols="20")
        ws_inst.append_row(['Instrument ID', 'Name', 'Price Rate (₹)', 'Available Slots', 'Status'])

    try: sh.worksheet("Bookings")
    except WorksheetNotFound: 
        ws_book = sh.add_worksheet(title="Bookings", rows="1000", cols="25")
        ws_book.append_row(['Booking ID', 'Timestamp', 'User Name', 'Role', 'Instrument', 'Date', 'Time Slot', 'Recommending Faculty', 'Payment Reference', 'Payment Date', 'Payment Status', 'Booking Status'])

    try: sh.worksheet("Users")
    except WorksheetNotFound: 
        ws_users = sh.add_worksheet(title="Users", rows="100", cols="20")
        ws_users.append_row(['User ID', 'Password', 'Role'])
        ws_users.append_row(['admin', hash_password('admin123'), 'Admin'])
        ws_users.append_row(['faculty1', hash_password('fac123'), 'Faculty'])
        ws_users.append_row(['scholar1', hash_password('sch123'), 'Research Scholar'])
        ws_users.append_row(['institute1', hash_password('inst123'), 'Research Institute'])
        ws_users.append_row(['industry1', hash_password('ind123'), 'Industry partner'])
        ws_users.append_row(['incharge1', hash_password('inc123'), 'Instrument Incharge'])
        
    return sh

sh = setup_database()

@st.cache_data(ttl=60)
def get_clean_dataframe(sheet_tab_name):
    try:
        local_sh = init_sheet()
        ws = local_sh.worksheet(sheet_tab_name)
        raw_data = ws.get_all_values()
        if len(raw_data) > 1:
            return pd.DataFrame(raw_data[1:], columns=[str(c).strip() for c in raw_data[0]])
        elif len(raw_data) == 1:
            return pd.DataFrame(columns=[str(c).strip() for c in raw_data[0]])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ Error fetching from '{sheet_tab_name}' tab: {e}")
        return pd.DataFrame()

def get_processed_bookings():
    df = get_clean_dataframe("Bookings").copy()
    if not df.empty and 'Date' in df.columns and 'Time Slot' in df.columns and 'Booking Status' in df.columns:
        current_time = datetime.now(IST)
        
        for idx, row in df.iterrows():
            if str(row['Booking Status']).strip() == 'Instrument Assigned':
                try:
                    date_str = str(row['Date']).strip()
                    time_slot = str(row['Time Slot']).strip()
                    
                    if " - " in time_slot:
                        end_time_str = time_slot.split(" - ")[1].replace("IST", "").strip()
                        dt_str = f"{date_str} {end_time_str}"
                        
                        naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
                        aware_dt = IST.localize(naive_dt)
                        
                        if current_time > aware_dt:
                            df.at[idx, 'Booking Status'] = 'Expired'
                except Exception:
                    pass
    return df

def col_letter(n):
    string = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        string = chr(65 + remainder) + string
    return string

def update_booking_in_sheet(booking_id, updates_dict):
    ws_book = sh.worksheet("Bookings")
    live_values = ws_book.get_all_values()
    headers = [str(c).strip() for c in live_values[0]]
    
    row_to_update = None
    for i, row in enumerate(live_values):
        if i > 0 and str(row[0]).strip() == str(booking_id).strip():
            row_to_update = i + 1 
            break
            
    if row_to_update:
        for col_name, new_val in updates_dict.items():
            if col_name in headers:
                col_letter_val = col_letter(headers.index(col_name) + 1)
                ws_book.update(values=[[new_val]], range_name=f"{col_letter_val}{row_to_update}")
        get_clean_dataframe.clear()
        return True
    return False

def update_instrument_in_sheet(inst_id, updates_dict):
    ws_inst = sh.worksheet("Instruments")
    live_values = ws_inst.get_all_values()
    headers = [str(c).strip() for c in live_values[0]]
    
    row_to_update = None
    for i, row in enumerate(live_values):
        if i > 0 and str(row[0]).strip() == str(inst_id).strip():
            row_to_update = i + 1 
            break
            
    if row_to_update:
        for col_name, new_val in updates_dict.items():
            if col_name in headers:
                col_letter_val = col_letter(headers.index(col_name) + 1)
                ws_inst.update(values=[[new_val]], range_name=f"{col_letter_val}{row_to_update}")
        get_clean_dataframe.clear()
        return True
    return False

# ==========================================
# 🖥️ LOGIN SYSTEM
# ==========================================
def login_page():
    st.markdown("<h2 style='text-align: center; color: #002147;'>University of Calcutta</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>Instrument Booking & Priority Portal</h4>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        user_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login", use_container_width=True):
            users_df = get_clean_dataframe("Users")
            if not users_df.empty and 'User ID' in users_df.columns:
                users_df['User ID'] = users_df['User ID'].astype(str).str.strip()
                users_df['Password'] = users_df['Password'].astype(str).str.strip()
                hashed_input = hash_password(str(password).strip())
                
                user_match = users_df[(users_df['User ID'] == str(user_id).strip()) & 
                                      ((users_df['Password'] == hashed_input) | (users_df['Password'] == str(password).strip()))]
                
                if not user_match.empty:
                    role = user_match.iloc[0]['Role']
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.user_name = user_id
                    
                    if role in CU_USERS: st.session_state.user_category = "CU User"
                    elif role in NON_CU_USERS: st.session_state.user_category = "Non-CU User"
                    elif role in STAFF_USERS: st.session_state.user_category = "Staff"
                    else: st.session_state.user_category = "System Admin"
                    
                    st.rerun()
                else:
                    st.error("🚨 Invalid User ID or Password")
            else:
                st.error("⚠️ Database Error: 'Users' tab is empty or invalid.")

# ==========================================
# 🛠️ SHARED USER INTERFACES
# ==========================================
def render_booking_form():
    st.subheader("New Booking Request")
    inst_df = get_clean_dataframe("Instruments")
    users_df = get_clean_dataframe("Users")
    
    if inst_df.empty or 'Name' not in inst_df.columns:
        st.info("System not ready. Admin must add instruments.")
        return
        
    # Read-Only Live Instrument Status (Visible to all users)
    st.write("**📡 Live Instrument Status Overview**")
    safe_inst_cols = [c for c in ['Instrument ID', 'Name', 'Price Rate (₹)', 'Status'] if c in inst_df.columns]
    styled_inst = inst_df[safe_inst_cols].style.apply(highlight_instruments, axis=1)
    st.dataframe(styled_inst, hide_index=True, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
        
    is_scholar = st.session_state.user_role == "Research Scholar"
    faculty_list = users_df[users_df['Role'] == 'Faculty']['User ID'].tolist() if not users_df.empty else []
    
    if is_scholar and not faculty_list:
        st.warning("No Faculty members found in the system. You cannot request recommendations until an Admin adds Faculty users.")
        return
        
    # Filter to strictly allow ONLY 'Working' or 'Active' instruments
    working_insts = inst_df[~inst_df['Status'].isin(['Not Working'])]
    
    if working_insts.empty:
        st.error("🛑 All instruments are currently marked as 'Not Working'. Bookings are temporarily paused.")
        return
        
    inst_options = []
    inst_map = {}
    for _, row in working_insts.iterrows():
        name = row['Name']
        price = row.get('Price Rate (₹)', '0')
        display_str = f"{name} - ₹{price}/hr"
        inst_options.append(display_str)
        inst_map[display_str] = name 
        
    with st.form("booking_form"):
        selected_display = st.selectbox("Select Instrument (Only Working Instruments Shown)", inst_options)
        selected_inst = inst_map[selected_display]
        date = st.date_input("Select Date")
        
        slot = st.selectbox("Select Time Slot", [
            "10:00 AM - 11:00 AM IST", 
            "11:00 AM - 12:00 PM IST", 
            "02:00 PM - 03:00 PM IST"
        ])
        
        selected_faculty = None
        if is_scholar:
            selected_faculty = st.selectbox("Send Recommendation Request To (Faculty)", faculty_list)
            
        if st.form_submit_button("Submit Request", type="primary"):
            all_bookings = get_processed_bookings()
            conflict = False
            
            if not all_bookings.empty and 'Date' in all_bookings.columns:
                existing = all_bookings[(all_bookings['Instrument'] == selected_inst) & 
                                        (all_bookings['Date'] == str(date)) & 
                                        (all_bookings['Time Slot'] == slot) &
                                        (all_bookings['Booking Status'].isin(['Awaiting Faculty Recommendation', 'Pending Admin Approval', 'Approved, Awaiting Payment', 'Payment Submitted, Awaiting Verification', 'Instrument Assigned']))]
                if not existing.empty: conflict = True
            
            if conflict:
                st.error("🚨 This time slot is already booked or pending. Please select another.")
            else:
                booking_id = f"BKG-{int(datetime.now(IST).timestamp())}"
                timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
                
                if is_scholar:
                    rec_faculty = selected_faculty
                    init_status = "Awaiting Faculty Recommendation"
                    msg = f"✅ Request sent to {rec_faculty} for recommendation!"
                else:
                    rec_faculty = "N/A - Direct"
                    init_status = "Pending Admin Approval"
                    msg = "✅ Booking submitted directly to Admin for approval!"
                    
                row_data = [booking_id, timestamp, st.session_state.user_name, st.session_state.user_role, 
                            selected_inst, str(date), slot, rec_faculty, "N/A", "N/A", "Pending", init_status]
                
                sh.worksheet("Bookings").append_row(row_data)
                st.success(msg)
                get_clean_dataframe.clear()
                time.sleep(1)
                st.rerun()

def render_payment_form():
    st.subheader("💳 Submit Payment Details")
    st.info("💡 You can only submit payment details for bookings that an Admin has already Approved.")
    
    all_bookings = get_processed_bookings()
    if not all_bookings.empty and 'User Name' in all_bookings.columns:
        my_approved = all_bookings[(all_bookings['User Name'] == st.session_state.user_name) & 
                                   (all_bookings['Booking Status'] == 'Approved, Awaiting Payment')].copy()
        
        if not my_approved.empty:
            st.dataframe(my_approved[['Booking ID', 'Instrument', 'Date', 'Time Slot', 'Booking Status']], hide_index=True)
            
            with st.form("payment_submission"):
                target_bkg = st.selectbox("Select Booking ID", my_approved['Booking ID'].tolist())
                pay_ref = st.text_input("Payment Reference Number (Transaction ID)")
                pay_date = st.date_input("Date of Payment")
                
                if st.form_submit_button("Submit Payment", type="primary"):
                    if not pay_ref:
                        st.error("🚨 Payment Reference Number is required.")
                    else:
                        updates = {
                            "Payment Reference": pay_ref,
                            "Payment Date": str(pay_date),
                            "Booking Status": "Payment Submitted, Awaiting Verification"
                        }
                        if update_booking_in_sheet(target_bkg, updates):
                            st.success(f"✅ Payment details sent to Admin for {target_bkg}.")
                            time.sleep(1)
                            st.rerun()
        else:
            st.success("You have no pending payments at this time.")
    else:
        st.info("System has no booking history.")

def render_my_status():
    st.subheader("My Booking History")
    all_bookings = get_processed_bookings()
    inst_df = get_clean_dataframe("Instruments")
    
    price_map = {}
    if not inst_df.empty and 'Name' in inst_df.columns:
        price_map = dict(zip(inst_df['Name'], inst_df.get('Price Rate (₹)', ['0']*len(inst_df))))
        
    if not all_bookings.empty and 'User Name' in all_bookings.columns:
        my_bookings = all_bookings[all_bookings['User Name'] == st.session_state.user_name].copy()
        if not my_bookings.empty:
            my_bookings['Price (₹/hr)'] = my_bookings['Instrument'].map(price_map).fillna("N/A")
            desired_cols = ['Date', 'Instrument', 'Price (₹/hr)', 'Time Slot', 'Payment Reference', 'Payment Status', 'Booking Status']
            safe_cols = [col for col in desired_cols if col in my_bookings.columns]
            
            styled_df = my_bookings[safe_cols].style.apply(highlight_rows, axis=1)
            st.dataframe(styled_df, hide_index=True, use_container_width=True)
        else:
            st.info("You have no booking history.")
    else:
        st.info("You have no booking history.")

# ==========================================
# 🎓 STANDARD USER DASHBOARD
# ==========================================
def standard_user_dashboard():
    st.title(f"Portal: {st.session_state.user_name} | {st.session_state.user_role} ({st.session_state.user_category})")
    tab1, tab2, tab3 = st.tabs(["📝 Book an Instrument", "💳 Make Payment", "🔔 My Status"])
    with tab1: render_booking_form()
    with tab2: render_payment_form()
    with tab3: render_my_status()

# ==========================================
# 🧑‍🏫 FACULTY DASHBOARD
# ==========================================
def faculty_dashboard():
    st.title(f"Faculty Portal: {st.session_state.user_name} ({st.session_state.user_category})")
    tab1, tab2, tab3, tab4 = st.tabs(["✅ Review Scholars", "📝 Book for Myself", "💳 Make Payment", "🔔 My Status"])
    
    with tab1:
        st.subheader("Research Scholar Requests Awaiting Your Recommendation")
        bookings_df = get_processed_bookings()
        inst_df = get_clean_dataframe("Instruments")
        
        price_map = {}
        if not inst_df.empty and 'Name' in inst_df.columns:
            price_map = dict(zip(inst_df['Name'], inst_df.get('Price Rate (₹)', ['0']*len(inst_df))))
        
        if not bookings_df.empty and 'Recommending Faculty' in bookings_df.columns:
            pending_reqs = bookings_df[(bookings_df['Recommending Faculty'] == st.session_state.user_name) & 
                                       (bookings_df['Booking Status'] == 'Awaiting Faculty Recommendation')].copy()
            
            if not pending_reqs.empty:
                pending_reqs['Price (₹/hr)'] = pending_reqs['Instrument'].map(price_map).fillna("N/A")
                safe_cols = [c for c in ['Booking ID', 'User Name', 'Instrument', 'Price (₹/hr)', 'Date', 'Time Slot'] if c in pending_reqs.columns]
                
                styled_reqs = pending_reqs[safe_cols].style.apply(highlight_rows, axis=1)
                st.dataframe(styled_reqs, hide_index=True)
                
                with st.form("faculty_review"):
                    target_bkg = st.selectbox("Select Booking ID to Review", pending_reqs['Booking ID'].tolist())
                    decision = st.selectbox("Action", ["Recommend to Admin", "Reject Request"])
                    
                    if st.form_submit_button("Submit Decision", type="primary"):
                        new_status = "Pending Admin Approval" if decision == "Recommend to Admin" else "Rejected by Faculty"
                        if update_booking_in_sheet(target_bkg, {"Booking Status": new_status}):
                            st.success(f"✅ {target_bkg} updated to: {new_status}")
                            time.sleep(1)
                            st.rerun()
            else:
                st.info("No pending scholar recommendations.")
        else:
            st.info("No bookings found in the system.")
            
    with tab2: render_booking_form()
    with tab3: render_payment_form()
    with tab4: render_my_status()

# ==========================================
# 🔧 INSTRUMENT INCHARGE DASHBOARD
# ==========================================
def incharge_dashboard():
    st.title(f"Instrument Incharge Portal: {st.session_state.user_name} ({st.session_state.user_category})")
    
    inst_df = get_clean_dataframe("Instruments")
    if not inst_df.empty:
        st.subheader("Manage Instrument Conditions")
        st.write("Marking an instrument as 'Not Working' instantly blocks users from booking it.")
        
        safe_inst_cols = [c for c in ['Instrument ID', 'Name', 'Price Rate (₹)', 'Status'] if c in inst_df.columns]
        styled_inst = inst_df[safe_inst_cols].style.apply(highlight_instruments, axis=1)
        st.dataframe(styled_inst, hide_index=True, use_container_width=True)
        
        st.markdown("---")
        with st.form("update_inst_status"):
            target_inst = st.selectbox("Select Instrument ID to Update", inst_df['Instrument ID'].tolist())
            new_status = st.selectbox("Update Condition Status", ["Working", "Not Working"])
            
            if st.form_submit_button("Apply Status Update", type="primary"):
                if update_instrument_in_sheet(target_inst, {"Status": new_status}):
                    st.success(f"✅ Instrument {target_inst} successfully marked as {new_status}.")
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("No instruments currently in the database.")

# ==========================================
# ⚙️ ADMIN DASHBOARD
# ==========================================
def admin_dashboard():
    st.title("Admin Control Panel")
    tab1, tab2, tab3 = st.tabs(["🚦 Approvals & Assignment Queue", "🔬 Manage Instruments", "👥 Manage Users"])
    
    with tab1:
        bookings_df = get_processed_bookings()
        inst_df = get_clean_dataframe("Instruments")
        
        price_map = {}
        if not inst_df.empty and 'Name' in inst_df.columns:
            price_map = dict(zip(inst_df['Name'], inst_df.get('Price Rate (₹)', ['0']*len(inst_df))))
            
        if not bookings_df.empty:
            st.subheader("Task Queue (Approvals & Payment Verifications)")
            action_statuses = ["Pending Admin Approval", "Payment Submitted, Awaiting Verification", "Waitlisted"]
            actionable = bookings_df[bookings_df['Booking Status'].isin(action_statuses)].copy()
            
            if not actionable.empty:
                actionable['Price (₹/hr)'] = actionable['Instrument'].map(price_map).fillna("N/A")
                safe_display_cols = [c for c in ['Booking ID', 'User Name', 'Instrument', 'Price (₹/hr)', 'Date', 'Time Slot', 'Payment Reference', 'Payment Date', 'Booking Status'] if c in actionable.columns]
                
                styled_actionable = actionable[safe_display_cols].sort_values(by=['Date']).style.apply(highlight_rows, axis=1)
                st.dataframe(styled_actionable, hide_index=True)
            else:
                st.info("Task Queue is currently empty.")
            
            st.markdown("---")
            st.subheader("Process a Booking")
            with st.form("admin_approval_form"):
                target_bkg = st.selectbox("Select Booking ID", bookings_df['Booking ID'].tolist())
                
                col1, col2 = st.columns(2)
                with col1:
                    new_payment = st.selectbox("Update Payment Status", ["Pending", "Paid", "Failed/Refunded"])
                with col2:
                    new_status = st.selectbox(
                        "Update Booking Status", 
                        ["Pending Admin Approval", "Approved, Awaiting Payment", "Payment Submitted, Awaiting Verification", "Waitlisted", "Rejected", "Instrument Assigned", "Completed", "Expired"]
                    )
                
                if st.form_submit_button("Apply Updates", type="primary"):
                    updates = {
                        "Payment Status": new_payment,
                        "Booking Status": new_status
                    }
                    if update_booking_in_sheet(target_bkg, updates):
                        st.success(f"✅ Booking {target_bkg} securely updated.")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("No bookings in system.")

    with tab2:
        st.subheader("Current Instruments Database")
        inst_df = get_clean_dataframe("Instruments")
        if not inst_df.empty:
            safe_inst_cols = [c for c in ['Instrument ID', 'Name', 'Price Rate (₹)', 'Available Slots', 'Status'] if c in inst_df.columns]
            styled_inst_admin = inst_df[safe_inst_cols].style.apply(highlight_instruments, axis=1)
            st.dataframe(styled_inst_admin, hide_index=True, use_container_width=True)
        else:
            st.info("No instruments found.")

        st.markdown("---")
        st.subheader("➕ Add New Instrument")
        with st.form("add_instrument"):
            col1, col2, col3 = st.columns(3)
            with col1: inst_id = st.text_input("Instrument ID")
            with col2: inst_name = st.text_input("Instrument Name")
            with col3: inst_price = st.number_input("Price/hr (₹)", min_value=0)
            
            if st.form_submit_button("Add Instrument", type="primary"):
                if inst_id and inst_name:
                    sh.worksheet("Instruments").append_row([inst_id, inst_name, inst_price, "Open", "Working"])
                    st.success(f"✅ {inst_name} added to the system.")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please provide an ID and Name.")

    with tab3:
        users_df = get_clean_dataframe("Users")
        if not users_df.empty:
            display_users = users_df.copy()
            if 'Password' in display_users.columns:
                display_users['Password'] = '******'
            st.dataframe(display_users, use_container_width=True, hide_index=True)
            
        st.markdown("---")
        with st.form("add_new_user"):
            st.subheader("Add New System User")
            new_uid = st.text_input("New User ID")
            new_pass = st.text_input("Temporary Password")
            new_role = st.selectbox("Select Role", ALL_ROLES)
            
            if new_role in CU_USERS: st.caption("🗂️ This role is categorized as a **CU User**.")
            elif new_role in NON_CU_USERS: st.caption("🗂️ This role is categorized as a **Non-CU User**.")
            elif new_role in STAFF_USERS: st.caption("🗂️ This role is categorized as **Staff**.")
            
            if st.form_submit_button("Add User", type="primary"):
                ws_users = sh.worksheet("Users")
                existing = pd.DataFrame(ws_users.get_all_records())
                if not existing.empty and str(new_uid).strip() in existing['User ID'].astype(str).str.strip().tolist():
                    st.error("🚨 User ID already exists.")
                elif not new_uid or not new_pass:
                    st.error("🚨 ID and Password required.")
                else:
                    ws_users.append_row([new_uid.strip(), hash_password(new_pass.strip()), new_role])
                    st.success(f"🎉 {new_uid} added as {new_role}!")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()

# ==========================================
# 🚀 APP ROUTING
# ==========================================
if not st.session_state.logged_in:
    login_page()
else:
    # 🚪 Logout Button (Top Right)
    col1, col2 = st.columns([9, 1])
    with col2:
        st.markdown('<div id="logout_marker"></div>', unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
            
    # 🖥️ Render the respective dashboard
    if st.session_state.user_role == "Admin": 
        admin_dashboard()
    elif st.session_state.user_role == "Faculty": 
        faculty_dashboard()
    elif st.session_state.user_role == "Instrument Incharge":
        incharge_dashboard()
    else: 
        standard_user_dashboard()
        
    # 🔄 Sync Button (Very Bottom)
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    col_s1, col_s2, col_s3 = st.columns([4, 2, 4])
    with col_s2:
        st.markdown('<div id="sync_marker"></div>', unsafe_allow_html=True)
        if st.button("🔄 Sync Application Data", use_container_width=True):
            get_clean_dataframe.clear()
            st.rerun()
