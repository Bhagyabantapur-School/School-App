import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
import time
import hashlib
import base64

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
    
    if status in ['Instrument Assigned', 'Space Assigned', 'Completed']:
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

def highlight_assets(row):
    """Dynamically checks for 'Status' in any column name and applies red if Not Working/Unavailable."""
    status = ''
    for col in row.index:
        if 'status' in str(col).lower():
            status = str(row.get(col, '')).strip()
            break
            
    if status in ['Not Working', 'Unavailable', 'Maintenance']:
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
    
    # Instruments
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

    # Spaces & Halls (NEW)
    try: sh.worksheet("Spaces")
    except WorksheetNotFound: 
        ws_space = sh.add_worksheet(title="Spaces", rows="100", cols="20")
        ws_space.append_row([
            'Space ID', 'Name', 'Campus Name', 'Building / Floor / Room No.', 
            'Capacity', 'Space Incharge', 'Contact Email', 'Price Rate (₹)', 'Status'
        ])

    try: sh.worksheet("Space Bookings")
    except WorksheetNotFound: 
        ws_sbook = sh.add_worksheet(title="Space Bookings", rows="1000", cols="25")
        ws_sbook.append_row(['Booking ID', 'Timestamp', 'User Name', 'Role', 'Space', 'Date', 'Time Slot', 'Recommending Faculty', 'Payment Reference', 'Payment Date', 'Payment Status', 'Booking Status'])

    # Users
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

def get_processed_bookings(sheet_name="Bookings", assigned_status="Instrument Assigned"):
    df = get_clean_dataframe(sheet_name).copy()
    if not df.empty and 'Date' in df.columns and 'Time Slot' in df.columns and 'Booking Status' in df.columns:
        current_time = datetime.now(IST)
        
        for idx, row in df.iterrows():
            if str(row['Booking Status']).strip() == assigned_status:
                try:
                    date_str = str(row['Date']).strip()
                    time_slot = str(row['Time Slot']).strip()
                    
                    if " - " in time_slot:
                        # Extract the end time safely, even if it has (5 Hours) attached after IST
                        end_time_str = time_slot.split(" - ")[1].split("IST")[0].strip()
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

def update_record_in_sheet(sheet_tab, id_col_index, target_id, updates_dict):
    ws = sh.worksheet(sheet_tab)
    live_values = ws.get_all_values()
    headers = [str(c).strip() for c in live_values[0]]
    
    row_to_update = None
    for i, row in enumerate(live_values):
        if i > 0 and str(row[id_col_index]).strip() == str(target_id).strip():
            row_to_update = i + 1 
            break
            
    if row_to_update:
        for col_name, new_val in updates_dict.items():
            if col_name in headers:
                col_letter_val = col_letter(headers.index(col_name) + 1)
                ws.update(values=[[new_val]], range_name=f"{col_letter_val}{row_to_update}")
        get_clean_dataframe.clear()
        return True
    return False

# ==========================================
# 🖼️ GLOBAL HEADER (Hardcoded Base64 Flexbox)
# ==========================================
def render_global_header():
    """Renders a flexbox HTML header using exact Base64 strings. Flattened to avoid Markdown code-block errors."""
    
    cu_img_html = '<img src="data:image/jpeg;base64,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" style="width: 100%; max-width: 80px; height: auto;" alt="RUSA Logo">'
    
    # 3. Create the unbreakable Flexbox layout. 
    # NOTE: Flattened into a single line to prevent Streamlit from treating it as a Markdown code block.
    header_html = f"""<div style="display: flex; justify-content: space-between; align-items: center; width: 100%; padding-bottom: 15px; border-bottom: 2px solid #f0f2f6; margin-bottom: 25px;"><div style="flex: 0 0 auto; min-width: 60px;">{cu_img_html}</div><div style="flex: 1 1 auto; text-align: center; padding: 0 10px;"><h2 style="color: #002147; margin: 0; padding: 0; font-size: clamp(1.1rem, 3.5vw, 2.2rem);">University of Calcutta</h2><h4 style="margin: 5px 0 0 0; padding: 0; font-size: clamp(0.8rem, 2vw, 1.2rem);">Instrument Booking & Priority Portal</h4></div><div style="flex: 0 0 auto; min-width: 60px; text-align: right;">{rusa_img_html}</div></div>"""
    
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
def render_instrument_booking_form():
    st.subheader("🔬 New Instrument Booking Request")
    inst_df = get_clean_dataframe("Instruments")
    users_df = get_clean_dataframe("Users")
    
    if inst_df.empty:
        st.info("System not ready. Admin must add instruments.")
        return
        
    st.write("**📡 Live Instrument Status Overview**")
    status_col_name = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
    
    safe_inst_cols = [c for c in ['Instrument ID', 'Name', 'Price Rate (₹)', status_col_name] if c in inst_df.columns]
    styled_inst = inst_df[safe_inst_cols].style.apply(highlight_assets, axis=1)
    st.dataframe(styled_inst, hide_index=True, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
        
    is_scholar = st.session_state.user_role == "Research Scholar"
    faculty_list = users_df[users_df['Role'] == 'Faculty']['User ID'].tolist() if not users_df.empty else []
    
    if is_scholar and not faculty_list:
        st.warning("No Faculty members found in the system. You cannot request recommendations until an Admin adds Faculty users.")
        return
        
    if status_col_name:
        working_insts = inst_df[~inst_df[status_col_name].isin(['Not Working', 'Maintenance', 'Unavailable'])]
    else:
        working_insts = inst_df
    
    if working_insts.empty:
        st.error("🛑 All instruments are currently unavailable.")
        return
        
    inst_options = []
    inst_map = {}
    for _, row in working_insts.iterrows():
        name = row.get('Name', 'Unknown')
        price = row.get('Price Rate (₹)', '0')
        display_str = f"{name} - ₹{price}/hr"
        inst_options.append(display_str)
        inst_map[display_str] = name 
        
    with st.form("instrument_booking_form"):
        selected_display = st.selectbox("Select Instrument", inst_options)
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
            all_bookings = get_processed_bookings("Bookings", "Instrument Assigned")
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

def render_space_booking_form():
    st.subheader("🏛️ New Space / Hall Booking Request")
    space_df = get_clean_dataframe("Spaces")
    users_df = get_clean_dataframe("Users")
    
    if space_df.empty:
        st.info("System not ready. Admin must add spaces/halls.")
        return
        
    st.write("**📡 Live Space Status Overview**")
    status_col_name = next((c for c in space_df.columns if 'status' in str(c).lower()), None)
    
    safe_space_cols = [c for c in ['Space ID', 'Name', 'Capacity', 'Price Rate (₹)', status_col_name] if c in space_df.columns]
    styled_space = space_df[safe_space_cols].style.apply(highlight_assets, axis=1)
    st.dataframe(styled_space, hide_index=True, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
        
    is_scholar = st.session_state.user_role == "Research Scholar"
    faculty_list = users_df[users_df['Role'] == 'Faculty']['User ID'].tolist() if not users_df.empty else []
    
    if is_scholar and not faculty_list:
        st.warning("No Faculty members found in the system. You cannot request recommendations until an Admin adds Faculty users.")
        return
        
    if status_col_name:
        working_spaces = space_df[~space_df[status_col_name].isin(['Not Working', 'Maintenance', 'Unavailable'])]
    else:
        working_spaces = space_df
    
    if working_spaces.empty:
        st.error("🛑 All spaces are currently marked as unavailable.")
        return
        
    space_options = []
    space_map = {}
    for _, row in working_spaces.iterrows():
        name = row.get('Name', 'Unknown')
        price = row.get('Price Rate (₹)', '0')
        display_str = f"{name} - ₹{price}/Slot"
        space_options.append(display_str)
        space_map[display_str] = name 
        
    with st.form("space_booking_form"):
        selected_display = st.selectbox("Select Space / Hall", space_options)
        selected_space = space_map[selected_display]
        date = st.date_input("Select Date")
        
        # New 5 to 6 Hour Slot Requirements
        slot = st.selectbox("Select Time Slot", [
            "09:00 AM - 02:00 PM IST (5 Hours)", 
            "10:00 AM - 04:00 PM IST (6 Hours)", 
            "02:00 PM - 07:00 PM IST (5 Hours)"
        ])
        
        selected_faculty = None
        if is_scholar:
            selected_faculty = st.selectbox("Send Recommendation Request To (Faculty)", faculty_list)
            
        if st.form_submit_button("Submit Request", type="primary"):
            all_s_bookings = get_processed_bookings("Space Bookings", "Space Assigned")
            conflict = False
            
            if not all_s_bookings.empty and 'Date' in all_s_bookings.columns:
                existing = all_s_bookings[(all_s_bookings['Space'] == selected_space) & 
                                        (all_s_bookings['Date'] == str(date)) & 
                                        (all_s_bookings['Time Slot'] == slot) &
                                        (all_s_bookings['Booking Status'].isin(['Awaiting Faculty Recommendation', 'Pending Admin Approval', 'Approved, Awaiting Payment', 'Payment Submitted, Awaiting Verification', 'Space Assigned']))]
                if not existing.empty: conflict = True
            
            if conflict:
                st.error("🚨 This time slot is already booked or pending. Please select another.")
            else:
                booking_id = f"SBKG-{int(datetime.now(IST).timestamp())}"
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
                            selected_space, str(date), slot, rec_faculty, "N/A", "N/A", "Pending", init_status]
                
                sh.worksheet("Space Bookings").append_row(row_data)
                st.success(msg)
                get_clean_dataframe.clear()
                time.sleep(1)
                st.rerun()

def render_payment_form():
    st.subheader("💳 Submit Payment Details")
    st.info("💡 You can only submit payment details for bookings that an Admin has already Approved.")
    
    pay_type = st.radio("What are you paying for?", ["Instrument Booking", "Space Booking"])
    sheet_target = "Bookings" if pay_type == "Instrument Booking" else "Space Bookings"
    assigned_tag = "Instrument Assigned" if pay_type == "Instrument Booking" else "Space Assigned"
    item_col = "Instrument" if pay_type == "Instrument Booking" else "Space"
    
    all_bookings = get_processed_bookings(sheet_target, assigned_tag)
    if not all_bookings.empty and 'User Name' in all_bookings.columns:
        my_approved = all_bookings[(all_bookings['User Name'] == st.session_state.user_name) & 
                                   (all_bookings['Booking Status'] == 'Approved, Awaiting Payment')].copy()
        
        if not my_approved.empty:
            st.dataframe(my_approved[['Booking ID', item_col, 'Date', 'Time Slot', 'Booking Status']], hide_index=True)
            
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
                        if update_record_in_sheet(sheet_target, 0, target_bkg, updates):
                            st.success(f"✅ Payment details sent to Admin for {target_bkg}.")
                            time.sleep(1)
                            st.rerun()
        else:
            st.success("You have no pending payments at this time.")
    else:
        st.info("System has no booking history for this category.")

def render_my_status():
    st.subheader("My Booking History")
    
    # Instruments
    st.markdown("**🔬 Instrument Bookings**")
    all_bookings = get_processed_bookings("Bookings", "Instrument Assigned")
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
            st.info("No instrument booking history.")
    else:
        st.info("No instrument booking history.")
        
    st.markdown("---")
    
    # Spaces
    st.markdown("**🏛️ Space / Hall Bookings**")
    all_s_bookings = get_processed_bookings("Space Bookings", "Space Assigned")
    space_df = get_clean_dataframe("Spaces")
    
    s_price_map = {}
    if not space_df.empty and 'Name' in space_df.columns:
        s_price_map = dict(zip(space_df['Name'], space_df.get('Price Rate (₹)', ['0']*len(space_df))))
        
    if not all_s_bookings.empty and 'User Name' in all_s_bookings.columns:
        my_s_bookings = all_s_bookings[all_s_bookings['User Name'] == st.session_state.user_name].copy()
        if not my_s_bookings.empty:
            my_s_bookings['Price (₹/Slot)'] = my_s_bookings['Space'].map(s_price_map).fillna("N/A")
            s_desired_cols = ['Date', 'Space', 'Price (₹/Slot)', 'Time Slot', 'Payment Reference', 'Payment Status', 'Booking Status']
            s_safe_cols = [col for col in s_desired_cols if col in my_s_bookings.columns]
            styled_s_df = my_s_bookings[s_safe_cols].style.apply(highlight_rows, axis=1)
            st.dataframe(styled_s_df, hide_index=True, use_container_width=True)
        else:
            st.info("No space booking history.")
    else:
        st.info("No space booking history.")

# ==========================================
# 🎓 STANDARD USER DASHBOARD
# ==========================================
def standard_user_dashboard():
    st.title(f"Portal: {st.session_state.user_name} | {st.session_state.user_role} ({st.session_state.user_category})")
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Book Instrument", "🏛️ Book Space", "💳 Make Payment", "🔔 My Status"])
    with tab1: render_instrument_booking_form()
    with tab2: render_space_booking_form()
    with tab3: render_payment_form()
    with tab4: render_my_status()

# ==========================================
# 🧑‍🏫 FACULTY DASHBOARD
# ==========================================
def faculty_dashboard():
    st.title(f"Faculty Portal: {st.session_state.user_name} ({st.session_state.user_category})")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["✅ Review Scholars", "📝 Book Instrument", "🏛️ Book Space", "💳 Make Payment", "🔔 My Status"])
    
    with tab1:
        st.subheader("Research Scholar Requests Awaiting Recommendation")
        
        req_type = st.radio("Select Request Type", ["Instruments", "Spaces"])
        sheet_target = "Bookings" if req_type == "Instruments" else "Space Bookings"
        assigned_tag = "Instrument Assigned" if req_type == "Instruments" else "Space Assigned"
        item_col = "Instrument" if req_type == "Instruments" else "Space"
        ref_sheet = "Instruments" if req_type == "Instruments" else "Spaces"
        price_label = 'Price (₹/hr)' if req_type == "Instruments" else 'Price (₹/Slot)'
        
        bookings_df = get_processed_bookings(sheet_target, assigned_tag)
        ref_df = get_clean_dataframe(ref_sheet)
        
        price_map = {}
        if not ref_df.empty and 'Name' in ref_df.columns:
            price_map = dict(zip(ref_df['Name'], ref_df.get('Price Rate (₹)', ['0']*len(ref_df))))
        
        if not bookings_df.empty and 'Recommending Faculty' in bookings_df.columns:
            pending_reqs = bookings_df[(bookings_df['Recommending Faculty'] == st.session_state.user_name) & 
                                       (bookings_df['Booking Status'] == 'Awaiting Faculty Recommendation')].copy()
            
            if not pending_reqs.empty:
                pending_reqs[price_label] = pending_reqs[item_col].map(price_map).fillna("N/A")
                safe_cols = [c for c in ['Booking ID', 'User Name', item_col, price_label, 'Date', 'Time Slot'] if c in pending_reqs.columns]
                
                styled_reqs = pending_reqs[safe_cols].style.apply(highlight_rows, axis=1)
                st.dataframe(styled_reqs, hide_index=True)
                
                with st.form("faculty_review"):
                    target_bkg = st.selectbox("Select Booking ID to Review", pending_reqs['Booking ID'].tolist())
                    decision = st.selectbox("Action", ["Recommend to Admin", "Reject Request"])
                    
                    if st.form_submit_button("Submit Decision", type="primary"):
                        new_status = "Pending Admin Approval" if decision == "Recommend to Admin" else "Rejected by Faculty"
                        if update_record_in_sheet(sheet_target, 0, target_bkg, {"Booking Status": new_status}):
                            st.success(f"✅ {target_bkg} updated to: {new_status}")
                            time.sleep(1)
                            st.rerun()
            else:
                st.info(f"No pending {req_type.lower()} recommendations.")
        else:
            st.info("No bookings found in the system.")
            
    with tab2: render_instrument_booking_form()
    with tab3: render_space_booking_form()
    with tab4: render_payment_form()
    with tab5: render_my_status()

# ==========================================
# 🔧 FACILITY INCHARGE DASHBOARD
# ==========================================
def incharge_dashboard():
    st.title(f"Facility Incharge Portal: {st.session_state.user_name} ({st.session_state.user_category})")
    
    manage_type = st.radio("Select Category to Manage", ["Instruments", "Spaces"])
    
    if manage_type == "Instruments":
        inst_df = get_clean_dataframe("Instruments")
        if not inst_df.empty:
            id_col = inst_df.columns[0]
            status_col = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
            
            if status_col:
                st.subheader("Manage Instrument Conditions")
                st.write("Marking an instrument as 'Not Working' instantly blocks users from booking it.")
                
                safe_inst_cols = [c for c in [id_col, 'Name', 'Price Rate (₹)', status_col] if c in inst_df.columns]
                styled_inst = inst_df[safe_inst_cols].style.apply(highlight_assets, axis=1)
                st.dataframe(styled_inst, hide_index=True, use_container_width=True)
                
                st.markdown("---")
                with st.form("update_inst_status"):
                    target_inst = st.selectbox("Select Instrument to Update", inst_df[id_col].tolist())
                    new_status = st.selectbox("Update Condition Status", ["Working", "Not Working"])
                    
                    if st.form_submit_button("Apply Status Update", type="primary"):
                        if update_record_in_sheet("Instruments", 0, target_inst, {status_col: new_status}):
                            st.success(f"✅ Instrument {target_inst} successfully marked as {new_status}.")
                            time.sleep(1)
                            st.rerun()
            else:
                st.error("⚠️ The 'Status' column is missing from your Instruments database.")
        else:
            st.info("No instruments currently in the database.")
            
    else:
        space_df = get_clean_dataframe("Spaces")
        if not space_df.empty:
            id_col = space_df.columns[0]
            status_col = next((c for c in space_df.columns if 'status' in str(c).lower()), None)
            
            if status_col:
                st.subheader("Manage Space Conditions")
                st.write("Marking a space as 'Unavailable' instantly blocks users from booking it.")
                
                safe_space_cols = [c for c in [id_col, 'Name', 'Capacity', status_col] if c in space_df.columns]
                styled_space = space_df[safe_space_cols].style.apply(highlight_assets, axis=1)
                st.dataframe(styled_space, hide_index=True, use_container_width=True)
                
                st.markdown("---")
                with st.form("update_space_status"):
                    target_space = st.selectbox("Select Space to Update", space_df[id_col].tolist())
                    new_status = st.selectbox("Update Condition Status", ["Available", "Unavailable", "Maintenance"])
                    
                    if st.form_submit_button("Apply Status Update", type="primary"):
                        if update_record_in_sheet("Spaces", 0, target_space, {status_col: new_status}):
                            st.success(f"✅ Space {target_space} successfully marked as {new_status}.")
                            time.sleep(1)
                            st.rerun()
            else:
                st.error("⚠️ The 'Status' column is missing from your Spaces database.")
        else:
            st.info("No spaces currently in the database.")

# ==========================================
# ⚙️ ADMIN DASHBOARD
# ==========================================
def admin_dashboard():
    st.title("Admin Control Panel")
    tab1, tab2, tab3, tab4 = st.tabs(["🚦 Approvals Queue", "🔬 Manage Instruments", "🏛️ Manage Spaces", "👥 Manage Users"])
    
    with tab1:
        req_type = st.radio("Queue Category", ["Instruments", "Spaces"])
        sheet_target = "Bookings" if req_type == "Instruments" else "Space Bookings"
        assigned_tag = "Instrument Assigned" if req_type == "Instruments" else "Space Assigned"
        item_col = "Instrument" if req_type == "Instruments" else "Space"
        ref_sheet = "Instruments" if req_type == "Instruments" else "Spaces"
        price_label = 'Price (₹/hr)' if req_type == "Instruments" else 'Price (₹/Slot)'
        
        bookings_df = get_processed_bookings(sheet_target, assigned_tag)
        ref_df = get_clean_dataframe(ref_sheet)
        
        price_map = {}
        if not ref_df.empty and 'Name' in ref_df.columns:
            price_map = dict(zip(ref_df['Name'], ref_df.get('Price Rate (₹)', ['0']*len(ref_df))))
            
        if not bookings_df.empty:
            st.subheader(f"Task Queue: {req_type}")
            action_statuses = ["Pending Admin Approval", "Payment Submitted, Awaiting Verification", "Waitlisted"]
            actionable = bookings_df[bookings_df['Booking Status'].isin(action_statuses)].copy()
            
            if not actionable.empty:
                actionable[price_label] = actionable[item_col].map(price_map).fillna("N/A")
                safe_display_cols = [c for c in ['Booking ID', 'User Name', item_col, price_label, 'Date', 'Time Slot', 'Payment Reference', 'Payment Date', 'Booking Status'] if c in actionable.columns]
                
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
                        ["Pending Admin Approval", "Approved, Awaiting Payment", "Payment Submitted, Awaiting Verification", "Waitlisted", "Rejected", assigned_tag, "Completed", "Expired"]
                    )
                
                if st.form_submit_button("Apply Updates", type="primary"):
                    updates = {
                        "Payment Status": new_payment,
                        "Booking Status": new_status
                    }
                    if update_record_in_sheet(sheet_target, 0, target_bkg, updates):
                        st.success(f"✅ Booking {target_bkg} securely updated.")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info(f"No {req_type.lower()} bookings in system.")

    with tab2:
        st.subheader("Current Instruments Database")
        inst_df = get_clean_dataframe("Instruments")
        if not inst_df.empty:
            status_col_name = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
            id_col = inst_df.columns[0]
            
            safe_inst_cols = [c for c in [id_col, 'Name', 'Make / Manufacturer', 'Department / Centre', 'Instrument Incharge', 'Price Rate (₹)', status_col_name] if c in inst_df.columns]
            styled_inst_admin = inst_df[safe_inst_cols].style.apply(highlight_assets, axis=1)
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
        st.subheader("Current Spaces & Halls Database")
        space_df = get_clean_dataframe("Spaces")
        if not space_df.empty:
            status_col_name = next((c for c in space_df.columns if 'status' in str(c).lower()), None)
            id_col = space_df.columns[0]
            
            safe_space_cols = [c for c in [id_col, 'Name', 'Capacity', 'Campus Name', 'Space Incharge', 'Price Rate (₹)', status_col_name] if c in space_df.columns]
            styled_space_admin = space_df[safe_space_cols].style.apply(highlight_assets, axis=1)
            st.dataframe(styled_space_admin, hide_index=True, use_container_width=True)
        else:
            st.info("No spaces found.")

        st.markdown("---")
        st.subheader("➕ Add New Space / Hall")
        
        with st.form("add_space"):
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1: space_id = st.text_input("Space ID*")
            with r1c2: space_name = st.text_input("Space / Hall Name*")
            with r1c3: space_price = st.number_input("Price Rate/Slot (₹)*", min_value=0)
            
            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1: space_campus = st.text_input("Campus Name")
            with r2c2: space_room = st.text_input("Building / Floor / Room No.")
            with r2c3: space_capacity = st.number_input("Max Capacity (Persons)", min_value=1, value=50)
            
            r3c1, r3c2, r3c3 = st.columns(3)
            with r3c1: 
                if incharge_list:
                    space_incharge = st.selectbox("Space Incharge", ["Select Incharge..."] + incharge_list)
                else:
                    space_incharge = st.selectbox("Space Incharge", ["No Incharge Found"])
                    st.caption("⚠️ Add an Instrument Incharge user first.")
            with r3c2: space_email = st.text_input("Contact Email")
            with r3c3: st.write("") # Spacer
            
            if st.form_submit_button("Add Space", type="primary"):
                if space_id and space_name:
                    final_space_incharge = space_incharge if space_incharge not in ["Select Incharge...", "No Incharge Found"] else ""
                    sh.worksheet("Spaces").append_row([
                        space_id, space_name, space_campus, space_room, 
                        space_capacity, final_space_incharge, space_email, 
                        space_price, "Available"
                    ])
                    st.success(f"✅ {space_name} added to the system.")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please provide at least a Space ID and Name.")

    with tab4:
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
