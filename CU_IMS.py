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

# ==========================================
# 🔒 SECURITY HELPER
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================
# 🧠 SESSION STATE
# ==========================================
for state in ['logged_in', 'user_role', 'user_name']:
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
    """Self-healing database setup: Recreates tabs if deleted without hitting API quotas."""
    sh = init_sheet()
    
    # 1. Instruments Tab
    try: 
        sh.worksheet("Instruments")
    except WorksheetNotFound: 
        ws_inst = sh.add_worksheet(title="Instruments", rows="100", cols="20")
        ws_inst.append_row(['Instrument ID', 'Name', 'Price Rate (₹)', 'Available Slots', 'Status'])

    # 2. Bookings Tab (Contains Recommending Teacher column)
    try: 
        sh.worksheet("Bookings")
    except WorksheetNotFound: 
        ws_book = sh.add_worksheet(title="Bookings", rows="1000", cols="20")
        ws_book.append_row(['Booking ID', 'Timestamp', 'User Name', 'Role', 'Instrument', 'Date', 'Time Slot', 'Recommending Teacher', 'Payment Status', 'Booking Status'])

    # 3. Users Tab
    try: 
        sh.worksheet("Users")
    except WorksheetNotFound: 
        ws_users = sh.add_worksheet(title="Users", rows="100", cols="20")
        ws_users.append_row(['User ID', 'Password', 'Role'])
        ws_users.append_row(['admin', hash_password('admin123'), 'Admin'])
        ws_users.append_row(['teacher1', hash_password('teach123'), 'Teacher'])
        ws_users.append_row(['student1', hash_password('pass123'), 'Student'])
        
    return sh

# 🚀 Run the Auto-Setup silently on load
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

def col_letter(n):
    """Converts column index to letter (e.g., 1 -> A, 2 -> B)"""
    string = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        string = chr(65 + remainder) + string
    return string

def update_booking_in_sheet(booking_id, new_payment=None, new_status=None):
    """Helper to dynamically update specific cells without breaking if columns move."""
    ws_book = sh.worksheet("Bookings")
    live_values = ws_book.get_all_values()
    headers = [str(c).strip() for c in live_values[0]]
    
    row_to_update = None
    for i, row in enumerate(live_values):
        if i > 0 and str(row[0]).strip() == str(booking_id).strip():
            row_to_update = i + 1 
            break
            
    if row_to_update:
        if new_payment and "Payment Status" in headers:
            pay_col = col_letter(headers.index("Payment Status") + 1)
            ws_book.update(values=[[new_payment]], range_name=f"{pay_col}{row_to_update}")
        if new_status and "Booking Status" in headers:
            stat_col = col_letter(headers.index("Booking Status") + 1)
            ws_book.update(values=[[new_status]], range_name=f"{stat_col}{row_to_update}")
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
                    st.session_state.logged_in = True
                    st.session_state.user_role = user_match.iloc[0]['Role']
                    st.session_state.user_name = user_id
                    st.rerun()
                else:
                    st.error("🚨 Invalid User ID or Password")
            else:
                st.error("⚠️ Database Error: 'Users' tab is empty or invalid.")

# ==========================================
# 🎓 STUDENT DASHBOARD
# ==========================================
def student_dashboard():
    st.title(f"Student Portal: {st.session_state.user_name}")
    tab1, tab2 = st.tabs(["📝 Book an Instrument", "🔔 My Status"])
    
    with tab1:
        inst_df = get_clean_dataframe("Instruments")
        users_df = get_clean_dataframe("Users")
        teachers = users_df[users_df['Role'] == 'Teacher']['User ID'].tolist() if not users_df.empty else []
        
        if inst_df.empty or not teachers:
            st.info("System not ready. Admin must add instruments and teachers.")
        else:
            with st.form("booking_form"):
                selected_inst = st.selectbox("Select Instrument", inst_df['Name'].tolist())
                date = st.date_input("Select Date")
                slot = st.selectbox("Select Time Slot", ["10:00 AM - 11:00 AM", "11:00 AM - 12:00 PM", "02:00 PM - 03:00 PM"])
                selected_teacher = st.selectbox("Send Recommendation Request To", teachers)
                
                if st.form_submit_button("Submit Request"):
                    all_bookings = get_clean_dataframe("Bookings")
                    conflict = False
                    if not all_bookings.empty and 'Date' in all_bookings.columns:
                        existing = all_bookings[(all_bookings['Instrument'] == selected_inst) & 
                                                (all_bookings['Date'] == str(date)) & 
                                                (all_bookings['Time Slot'] == slot) &
                                                (all_bookings['Booking Status'].isin(['Awaiting Teacher Recommendation', 'Pending Admin Approval', 'Approved']))]
                        if not existing.empty: conflict = True
                    
                    if conflict:
                        st.error("🚨 This time slot is already booked or pending. Please select another.")
                    else:
                        booking_id = f"BKG-{int(datetime.now(IST).timestamp())}"
                        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                        row_data = [booking_id, timestamp, st.session_state.user_name, st.session_state.user_role, 
                                    selected_inst, str(date), slot, selected_teacher, "Pending", "Awaiting Teacher Recommendation"]
                        sh.worksheet("Bookings").append_row(row_data)
                        st.success("✅ Request sent to teacher for recommendation!")
                        get_clean_dataframe.clear()
                        time.sleep(1)
                        st.rerun()

    with tab2:
        all_bookings = get_clean_dataframe("Bookings")
        if not all_bookings.empty and 'User Name' in all_bookings.columns:
            my_bookings = all_bookings[all_bookings['User Name'] == st.session_state.user_name]
            if not my_bookings.empty:
                st.dataframe(my_bookings[['Date', 'Instrument', 'Time Slot', 'Recommending Teacher', 'Payment Status', 'Booking Status']], hide_index=True)
            else:
                st.info("You have no booking history.")
        else:
            st.info("You have no booking history.")

# ==========================================
# 🧑‍🏫 TEACHER DASHBOARD
# ==========================================
def teacher_dashboard():
    st.title(f"Teacher Portal: {st.session_state.user_name}")
    st.subheader("Student Requests Awaiting Your Recommendation")
    
    bookings_df = get_clean_dataframe("Bookings")
    
    if not bookings_df.empty and 'Recommending Teacher' in bookings_df.columns:
        pending_reqs = bookings_df[(bookings_df['Recommending Teacher'] == st.session_state.user_name) & 
                                   (bookings_df['Booking Status'] == 'Awaiting Teacher Recommendation')]
        
        if not pending_reqs.empty:
            st.dataframe(pending_reqs[['Booking ID', 'User Name', 'Instrument', 'Date', 'Time Slot']], hide_index=True)
            
            with st.form("teacher_review"):
                target_bkg = st.selectbox("Select Booking ID to Review", pending_reqs['Booking ID'].tolist())
                decision = st.selectbox("Action", ["Recommend to Admin", "Reject Request"])
                
                if st.form_submit_button("Submit Decision", type="primary"):
                    new_status = "Pending Admin Approval" if decision == "Recommend to Admin" else "Rejected by Teacher"
                    if update_booking_in_sheet(target_bkg, new_status=new_status):
                        st.success(f"✅ {target_bkg} updated to: {new_status}")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("You have no pending student recommendations to review.")
    else:
        st.info("No bookings found in the system.")

# ==========================================
# ⚙️ ADMIN DASHBOARD
# ==========================================
def admin_dashboard():
    st.title("Admin Control Panel")
    tab1, tab2, tab3 = st.tabs(["🚦 Queue & Payment", "🔬 Manage Instruments", "👥 Manage Users"])
    
    with tab1:
        bookings_df = get_clean_dataframe("Bookings")
        if not bookings_df.empty:
            st.write("**Queue Overview (Awaiting Payment/Admin Approval)**")
            actionable = bookings_df[bookings_df['Booking Status'].isin(["Pending Admin Approval", "Approved", "Waitlisted"])]
            st.dataframe(actionable.sort_values(by=['Date', 'Timestamp']), hide_index=True)
            
            st.markdown("---")
            with st.form("admin_approval_form"):
                target_bkg = st.selectbox("Select Booking ID", bookings_df['Booking ID'].tolist())
                new_payment = st.selectbox("Payment Status", ["Pending", "Paid", "Failed/Refunded"])
                new_status = st.selectbox("Booking Status", ["Pending Admin Approval", "Approved", "Waitlisted", "Rejected", "Completed"])
                
                if st.form_submit_button("Process Payment & Update Status", type="primary"):
                    if update_booking_in_sheet(target_bkg, new_payment, new_status):
                        st.success(f"✅ Booking {target_bkg} securely updated.")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("No bookings in system.")

    with tab2:
        with st.form("add_instrument"):
            col1, col2, col3 = st.columns(3)
            with col1: inst_id = st.text_input("Instrument ID")
            with col2: inst_name = st.text_input("Instrument Name")
            with col3: inst_price = st.number_input("Price/hr (₹)", min_value=0)
            
            if st.form_submit_button("Add Instrument"):
                if inst_id and inst_name:
                    sh.worksheet("Instruments").append_row([inst_id, inst_name, inst_price, "Open", "Active"])
                    st.success(f"✅ {inst_name} added.")
                    get_clean_dataframe.clear()
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
            new_uid = st.text_input("New User ID")
            new_pass = st.text_input("Temporary Password")
            new_role = st.selectbox("Select Role", ["Student", "Teacher", "Admin"])
            
            if st.form_submit_button("Add User", type="primary"):
                ws_users = sh.worksheet("Users")
                existing = pd.DataFrame(ws_users.get_all_records())
                if not existing.empty and str(new_uid).strip() in existing['User ID'].astype(str).str.strip().tolist():
                    st.error("🚨 User ID already exists.")
                else:
                    ws_users.append_row([new_uid.strip(), hash_password(new_pass.strip()), new_role])
                    st.success(f"🎉 {new_uid} added!")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()

# ==========================================
# 🚀 APP ROUTING
# ==========================================
if not st.session_state.logged_in:
    login_page()
else:
    col1, col2 = st.columns([8, 1])
    with col2:
        if st.button("Logout"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
            
    if st.session_state.user_role == "Admin": admin_dashboard()
    elif st.session_state.user_role == "Teacher": teacher_dashboard()
    else: student_dashboard()
