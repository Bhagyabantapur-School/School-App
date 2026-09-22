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
ALL_ROLES = ["Admin"] + CU_USERS + NON_CU_USERS

# ==========================================
# 🔒 SECURITY HELPER
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
    
    # 1. Instruments Tab
    try: 
        sh.worksheet("Instruments")
    except WorksheetNotFound: 
        ws_inst = sh.add_worksheet(title="Instruments", rows="100", cols="20")
        ws_inst.append_row(['Instrument ID', 'Name', 'Price Rate (₹)', 'Available Slots', 'Status'])

    # 2. Bookings Tab 
    try: 
        sh.worksheet("Bookings")
    except WorksheetNotFound: 
        ws_book = sh.add_worksheet(title="Bookings", rows="1000", cols="20")
        ws_book.append_row(['Booking ID', 'Timestamp', 'User Name', 'Role', 'Instrument', 'Date', 'Time Slot', 'Recommending Faculty', 'Payment Status', 'Booking Status'])

    # 3. Users Tab
    try: 
        sh.worksheet("Users")
    except WorksheetNotFound: 
        ws_users = sh.add_worksheet(title="Users", rows="100", cols="20")
        ws_users.append_row(['User ID', 'Password', 'Role'])
        ws_users.append_row(['admin', hash_password('admin123'), 'Admin'])
        ws_users.append_row(['faculty1', hash_password('fac123'), 'Faculty'])
        ws_users.append_row(['scholar1', hash_password('sch123'), 'Research Scholar'])
        ws_users.append_row(['institute1', hash_password('inst123'), 'Research Institute'])
        ws_users.append_row(['industry1', hash_password('ind123'), 'Industry partner'])
        
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

def col_letter(n):
    string = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        string = chr(65 + remainder) + string
    return string

def update_booking_in_sheet(booking_id, new_payment=None, new_status=None):
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
                    role = user_match.iloc[0]['Role']
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.user_name = user_id
                    
                    if role in CU_USERS: st.session_state.user_category = "CU User"
                    elif role in NON_CU_USERS: st.session_state.user_category = "Non-CU User"
                    else: st.session_state.user_category = "System Admin"
                    
                    st.rerun()
                else:
                    st.error("🚨 Invalid User ID or Password")
            else:
                st.error("⚠️ Database Error: 'Users' tab is empty or invalid.")

# ==========================================
# 🛠️ SHARED BOOKING INTERFACE
# ==========================================
def render_booking_form():
    st.subheader("New Booking Request")
    inst_df = get_clean_dataframe("Instruments")
    users_df = get_clean_dataframe("Users")
    
    if inst_df.empty or 'Name' not in inst_df.columns:
        st.info("System not ready. Admin must add instruments.")
        return
        
    is_scholar = st.session_state.user_role == "Research Scholar"
    faculty_list = users_df[users_df['Role'] == 'Faculty']['User ID'].tolist() if not users_df.empty else []
    
    if is_scholar and not faculty_list:
        st.warning("No Faculty members found in the system. You cannot request recommendations until an Admin adds Faculty users.")
        return
        
    # Format Instruments with Prices for the Dropdown
    inst_options = []
    inst_map = {}
    for _, row in inst_df.iterrows():
        name = row['Name']
        price = row.get('Price Rate (₹)', '0')
        display_str = f"{name} - ₹{price}/hr"
        inst_options.append(display_str)
        inst_map[display_str] = name # Keep track of actual name to save in DB
        
    with st.form("booking_form"):
        selected_display = st.selectbox("Select Instrument", inst_options)
        selected_inst = inst_map[selected_display] # Extract clean name for database
        
        date = st.date_input("Select Date")
        slot = st.selectbox("Select Time Slot", ["10:00 AM - 11:00 AM", "11:00 AM - 12:00 PM", "02:00 PM - 03:00 PM"])
        
        selected_faculty = None
        if is_scholar:
            selected_faculty = st.selectbox("Send Recommendation Request To (Faculty)", faculty_list)
            
        if st.form_submit_button("Submit Request", type="primary"):
            all_bookings = get_clean_dataframe("Bookings")
            conflict = False
            
            if not all_bookings.empty and 'Date' in all_bookings.columns:
                existing = all_bookings[(all_bookings['Instrument'] == selected_inst) & 
                                        (all_bookings['Date'] == str(date)) & 
                                        (all_bookings['Time Slot'] == slot) &
                                        (all_bookings['Booking Status'].isin(['Awaiting Faculty Recommendation', 'Pending Admin Approval', 'Approved']))]
                if not existing.empty: conflict = True
            
            if conflict:
                st.error("🚨 This time slot is already booked or pending. Please select another.")
            else:
                booking_id = f"BKG-{int(datetime.now(IST).timestamp())}"
                timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                
                if is_scholar:
                    rec_faculty = selected_faculty
                    init_status = "Awaiting Faculty Recommendation"
                    msg = f"✅ Request sent to {rec_faculty} for recommendation!"
                else:
                    rec_faculty = "N/A - Direct"
                    init_status = "Pending Admin Approval"
                    msg = "✅ Booking submitted directly to Admin for approval!"
                    
                row_data = [booking_id, timestamp, st.session_state.user_name, st.session_state.user_role, 
                            selected_inst, str(date), slot, rec_faculty, "Pending", init_status]
                
                sh.worksheet("Bookings").append_row(row_data)
                st.success(msg)
                get_clean_dataframe.clear()
                time.sleep(1)
                st.rerun()

def render_my_status():
    st.subheader("My Booking History")
    all_bookings = get_clean_dataframe("Bookings")
    inst_df = get_clean_dataframe("Instruments")
    
    # Create a pricing dictionary to map into the queue
    price_map = {}
    if not inst_df.empty and 'Name' in inst_df.columns:
        price_map = dict(zip(inst_df['Name'], inst_df.get('Price Rate (₹)', ['0']*len(inst_df))))
        
    if not all_bookings.empty and 'User Name' in all_bookings.columns:
        my_bookings = all_bookings[all_bookings['User Name'] == st.session_state.user_name].copy()
        if not my_bookings.empty:
            my_bookings['Price (₹/hr)'] = my_bookings['Instrument'].map(price_map).fillna("N/A")
            
            desired_cols = ['Date', 'Instrument', 'Price (₹/hr)', 'Time Slot', 'Recommending Faculty', 'Payment Status', 'Booking Status']
            safe_cols = [col for col in desired_cols if col in my_bookings.columns]
            
            st.dataframe(my_bookings[safe_cols], hide_index=True)
        else:
            st.info("You have no booking history.")
    else:
        st.info("You have no booking history.")

# ==========================================
# 🎓 STANDARD USER DASHBOARD (Scholars, Inst, Ind)
# ==========================================
def standard_user_dashboard():
    st.title(f"Portal: {st.session_state.user_name} | {st.session_state.user_role} ({st.session_state.user_category})")
    tab1, tab2 = st.tabs(["📝 Book an Instrument", "🔔 My Status"])
    with tab1: render_booking_form()
    with tab2: render_my_status()

# ==========================================
# 🧑‍🏫 FACULTY DASHBOARD (Bookings + Approvals)
# ==========================================
def faculty_dashboard():
    st.title(f"Faculty Portal: {st.session_state.user_name} ({st.session_state.user_category})")
    tab1, tab2, tab3 = st.tabs(["✅ Review Scholars", "📝 Book for Myself", "🔔 My Status"])
    
    with tab1:
        st.subheader("Research Scholar Requests Awaiting Your Recommendation")
        bookings_df = get_clean_dataframe("Bookings")
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
                st.dataframe(pending_reqs[safe_cols], hide_index=True)
                
                with st.form("faculty_review"):
                    target_bkg = st.selectbox("Select Booking ID to Review", pending_reqs['Booking ID'].tolist())
                    decision = st.selectbox("Action", ["Recommend to Admin", "Reject Request"])
                    
                    if st.form_submit_button("Submit Decision", type="primary"):
                        new_status = "Pending Admin Approval" if decision == "Recommend to Admin" else "Rejected by Faculty"
                        if update_booking_in_sheet(target_bkg, new_status=new_status):
                            st.success(f"✅ {target_bkg} updated to: {new_status}")
                            time.sleep(1)
                            st.rerun()
            else:
                st.info("No pending scholar recommendations.")
        else:
            st.info("No bookings found in the system.")
            
    with tab2: render_booking_form()
    with tab3: render_my_status()

# ==========================================
# ⚙️ ADMIN DASHBOARD
# ==========================================
def admin_dashboard():
    st.title("Admin Control Panel")
    tab1, tab2, tab3 = st.tabs(["🚦 Queue & Payment", "🔬 Manage Instruments", "👥 Manage Users"])
    
    with tab1:
        bookings_df = get_clean_dataframe("Bookings")
        inst_df = get_clean_dataframe("Instruments")
        
        price_map = {}
        if not inst_df.empty and 'Name' in inst_df.columns:
            price_map = dict(zip(inst_df['Name'], inst_df.get('Price Rate (₹)', ['0']*len(inst_df))))
            
        if not bookings_df.empty:
            st.write("**Queue Overview (Awaiting Payment/Admin Approval)**")
            actionable = bookings_df[bookings_df['Booking Status'].isin(["Pending Admin Approval", "Approved", "Waitlisted"])].copy()
            
            if not actionable.empty:
                actionable['Price (₹/hr)'] = actionable['Instrument'].map(price_map).fillna("N/A")
                
                # Reorder columns to put price cleanly next to the instrument
                cols = list(actionable.columns)
                if 'Instrument' in cols and 'Price (₹/hr)' in cols:
                    cols.insert(cols.index('Instrument') + 1, cols.pop(cols.index('Price (₹/hr)')))
                    
                st.dataframe(actionable[cols].sort_values(by=['Date', 'Timestamp']), hide_index=True)
            else:
                st.info("Queue is currently empty.")
            
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
            st.subheader("Add New System User")
            new_uid = st.text_input("New User ID")
            new_pass = st.text_input("Temporary Password")
            new_role = st.selectbox("Select Role", ALL_ROLES)
            
            if new_role in CU_USERS: st.caption("🗂️ This role is categorized as a **CU User**.")
            elif new_role in NON_CU_USERS: st.caption("🗂️ This role is categorized as a **Non-CU User**.")
            
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
    col1, col2 = st.columns([8, 1])
    with col2:
        if st.button("Logout"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
            
    if st.session_state.user_role == "Admin": admin_dashboard()
    elif st.session_state.user_role == "Faculty": faculty_dashboard()
    else: standard_user_dashboard()
