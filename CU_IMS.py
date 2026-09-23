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
    """Dynamically checks for 'Status' in any column name and applies red if Not Working."""
    status = ''
    for col in row.index:
        if 'status' in str(col).lower():
            status = str(row.get(col, '')).strip()
            break
            
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
        ws_inst = sh.add_worksheet(title="Instruments", rows="100", cols="25")
        ws_inst.append_row([
            'Instrument ID', 'Name', 'Make / Manufacturer', 'Serial No.', 'Unit No.', 
            'Campus Name', 'Department / Centre', 'Building / Floor / Room No.', 
            'Instrument Incharge', 'Designation of In-charge', 'Contact Email', 
            'Price Rate (₹)', 'Available Slots', 'Status'
        ])

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
# 🖼️ GLOBAL HEADER (Hardcoded Base64 Flexbox)
# ==========================================
def render_global_header():
    """Renders a flexbox HTML header using exact Base64 strings. Will NEVER stack on mobile."""
    
    # 1. Base64 injected directly from user prompt
    cu_img_html = '<img src="data:image/jpeg;base64,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" style="width: 100%; max-width: 80px; height: auto;" alt="CU Logo">'
    
    # 2. Base64 injected directly from user prompt
    rusa_img_html = '<img src="data:image/jpeg;base64,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" style="width: 100%; max-width: 80px; height: auto;" alt="RUSA Logo">'
    
    # 3. Create the unbreakable Flexbox layout
    header_html = f"""
    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; padding-bottom: 15px; border-bottom: 2px solid #f0f2f6; margin-bottom: 25px;">
        
        <!-- Left Logo Container -->
        <div style="flex: 0 0 auto; min-width: 60px;">
            {cu_img_html}
        </div>
        
        <!-- Center Titles Container -->
        <div style="flex: 1 1 auto; text-align: center; padding: 0 10px;">
            <h2 style="color: #002147; margin: 0; padding: 0; font-size: clamp(1.1rem, 3.5vw, 2.2rem);">University of Calcutta</h2>
            <h4 style="margin: 5px 0 0 0; padding: 0; font-size: clamp(0.8rem, 2vw, 1.2rem);">Instrument Booking & Priority Portal</h4>
        </div>
        
        <!-- Right Logo Container -->
        <div style="flex: 0 0 auto; min-width: 60px; text-align: right;">
            {rusa_img_html}
        </div>
        
    </div>
    """
    
    # 4. Render exactly as HTML into Streamlit
    st.markdown(header_html, unsafe_allow_html=True)

# ==========================================
# 🖥️ LOGIN SYSTEM
# ==========================================
def login_page():
    with st.form("login_form"):
        st.write("### Sign In")
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
                    role = user_match.iloc[0]['Role'].strip()
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.user_name = user_id
                    
                    if role == "Admin": st.session_state.user_category = "System Admin"
                    elif role in CU_USERS: st.session_state.user_category = "CU User"
                    elif role in NON_CU_USERS: st.session_state.user_category = "Non-CU User"
                    elif role in STAFF_USERS: st.session_state.user_category = "Staff"
                    else: st.session_state.user_category = "Custom User"
                    
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
    
    if inst_df.empty:
        st.info("System not ready. Admin must add instruments.")
        return
        
    st.write("**📡 Live Instrument Status Overview**")
    status_col_name = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
    
    safe_inst_cols = [c for c in ['Instrument ID', 'Name', 'Price Rate (₹)', status_col_name] if c in inst_df.columns]
    styled_inst = inst_df[safe_inst_cols].style.apply(highlight_instruments, axis=1)
    st.dataframe(styled_inst, hide_index=True, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
        
    is_scholar = st.session_state.user_role == "Research Scholar"
    faculty_list = users_df[users_df['Role'] == 'Faculty']['User ID'].tolist() if not users_df.empty else []
    
    if is_scholar and not faculty_list:
        st.warning("No Faculty members found in the system. You cannot request recommendations until an Admin adds Faculty users.")
        return
        
    if status_col_name:
        working_insts = inst_df[~inst_df[status_col_name].isin(['Not Working'])]
    else:
        working_insts = inst_df
    
    if working_insts.empty:
        st.error("🛑 All instruments are currently marked as 'Not Working'. Bookings are temporarily paused.")
        return
        
    inst_options = []
    inst_map = {}
    for _, row in working_insts.iterrows():
        name = row.get('Name', 'Unknown')
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
        id_col = inst_df.columns[0]
        status_col = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
        
        if status_col:
            st.subheader("Manage Instrument Conditions")
            st.write("Marking an instrument as 'Not Working' instantly blocks users from booking it.")
            
            safe_inst_cols = [c for c in [id_col, 'Name', 'Price Rate (₹)', status_col] if c in inst_df.columns]
            styled_inst = inst_df[safe_inst_cols].style.apply(highlight_instruments, axis=1)
            st.dataframe(styled_inst, hide_index=True, use_container_width=True)
            
            st.markdown("---")
            with st.form("update_inst_status"):
                target_inst = st.selectbox("Select Instrument to Update", inst_df[id_col].tolist())
                new_status = st.selectbox("Update Condition Status", ["Working", "Not Working"])
                
                if st.form_submit_button("Apply Status Update", type="primary"):
                    if update_instrument_in_sheet(target_inst, {status_col: new_status}):
                        st.success(f"✅ Instrument {target_inst} successfully marked as {new_status}.")
                        time.sleep(1)
                        st.rerun()
        else:
            st.error("⚠️ The 'Status' column is missing from your Instruments database.")
            st.write("🔍 **Debug Info: Exact Headers Seen by App:**")
            st.code(list(inst_df.columns))
            st.info("Please ensure one of these headers contains the word 'Status'.")
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
            status_col_name = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
            id_col = inst_df.columns[0]
            
            safe_inst_cols = [c for c in [id_col, 'Name', 'Make / Manufacturer', 'Department / Centre', 'Instrument Incharge', 'Price Rate (₹)', status_col_name] if c in inst_df.columns]
            styled_inst_admin = inst_df[safe_inst_cols].style.apply(highlight_instruments, axis=1)
            st.dataframe(styled_inst_admin, hide_index=True, use_container_width=True)
        else:
            st.info("No instruments found.")

        st.markdown("---")
        st.subheader("➕ Add New Instrument")
        
        users_df = get_clean_dataframe("Users")
        incharge_list = []
        if not users_df.empty and 'Role' in users_df.columns and 'User ID' in users_df.columns:
            incharge_list = users_df[users_df['Role'] == 'Instrument Incharge']['User ID'].tolist()
            
        with st.form("add_instrument"):
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1: inst_id = st.text_input("Instrument ID*")
            with r1c2: inst_name = st.text_input("Instrument Name*")
            with r1c3: inst_price = st.number_input("Price Rate/hr (₹)*", min_value=0)
            
            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1: inst_make = st.text_input("Make / Manufacturer")
            with r2c2: inst_serial = st.text_input("Serial No.")
            with r2c3: inst_unit = st.text_input("Unit No.")
            
            r3c1, r3c2, r3c3 = st.columns(3)
            with r3c1: inst_campus = st.text_input("Campus Name")
            with r3c2: inst_dept = st.text_input("Department / Centre")
            with r3c3: inst_room = st.text_input("Building / Floor / Room No.")
            
            r4c1, r4c2, r4c3 = st.columns(3)
            with r4c1: 
                if incharge_list:
                    inst_incharge = st.selectbox("Instrument Incharge", ["Select Incharge..."] + incharge_list)
                else:
                    inst_incharge = st.selectbox("Instrument Incharge", ["No Incharge Found"])
                    st.caption("⚠️ Add an Instrument Incharge user first.")
            with r4c2: inst_desig = st.text_input("Designation of In-charge")
            with r4c3: inst_email = st.text_input("Contact Email")
            
            if st.form_submit_button("Add Instrument", type="primary"):
                if inst_id and inst_name:
                    
                    final_incharge = inst_incharge if inst_incharge not in ["Select Incharge...", "No Incharge Found"] else ""
                    
                    sh.worksheet("Instruments").append_row([
                        inst_id, inst_name, inst_make, inst_serial, inst_unit, 
                        inst_campus, inst_dept, inst_room, final_incharge, 
                        inst_desig, inst_email, inst_price, "Open", "Working"
                    ])
                    st.success(f"✅ {inst_name} added to the system.")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please provide at least an Instrument ID and Name.")

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
            
            existing_roles = users_df['Role'].unique().tolist() if not users_df.empty and 'Role' in users_df.columns else []
            combined_roles = sorted(list(set(ALL_ROLES + existing_roles)))
            combined_roles.append("➕ Create New Role...")
            
            selected_role = st.selectbox("Select Role", combined_roles)
            custom_role = st.text_input("Type New Role Name (Required only if '➕ Create New Role...' is selected)")
            
            st.caption("💡 *Note: Predefined roles have specialized dashboards. New custom roles will receive the Standard User portal.*")
            
            if st.form_submit_button("Add User", type="primary"):
                final_role = custom_role.strip() if selected_role == "➕ Create New Role..." else selected_role.strip()
                
                ws_users = sh.worksheet("Users")
                existing = pd.DataFrame(ws_users.get_all_records())
                if not existing.empty and str(new_uid).strip() in existing['User ID'].astype(str).str.strip().tolist():
                    st.error("🚨 User ID already exists.")
                elif not new_uid or not new_pass:
                    st.error("🚨 ID and Password required.")
                elif not final_role:
                    st.error("🚨 Role name cannot be empty.")
                else:
                    ws_users.append_row([new_uid.strip(), hash_password(new_pass.strip()), final_role])
                    st.success(f"🎉 {new_uid} added as {final_role}!")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()

# ==========================================
# 🚀 APP ROUTING
# ==========================================
render_global_header()

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
