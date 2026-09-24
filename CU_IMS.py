import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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
    sh = init_sheet()
    try:
        existing_tabs = [ws.title for ws in sh.worksheets()]
        
        if "Instruments" not in existing_tabs:
            ws_inst = sh.add_worksheet(title="Instruments", rows="100", cols="25")
            ws_inst.append_row([
                'Instrument ID', 'Name', 'Make / Manufacturer', 'Serial No.', 'Unit No.', 
                'Campus Name', 'Department / Centre', 'Building / Floor / Room No.', 
                'Instrument Incharge', 'Designation of In-charge', 'Contact Email', 
                'Price Rate (₹)', 'Available Slots', 'Status'
            ])

        if "Bookings" not in existing_tabs:
            ws_book = sh.add_worksheet(title="Bookings", rows="1000", cols="25")
            ws_book.append_row(['Booking ID', 'Timestamp', 'User Name', 'Role', 'Instrument', 'Date', 'Time Slot', 'Recommending Faculty', 'Payment Reference', 'Payment Date', 'Payment Status', 'Booking Status'])

        if "Spaces" not in existing_tabs:
            ws_space = sh.add_worksheet(title="Spaces", rows="100", cols="20")
            ws_space.append_row([
                'Space ID', 'Name', 'Campus Name', 'Building / Floor / Room No.', 
                'Capacity', 'Space Incharge', 'Contact Email', 'Price Rate (₹)', 'Status'
            ])

        if "Space Bookings" not in existing_tabs:
            ws_sbook = sh.add_worksheet(title="Space Bookings", rows="1000", cols="25")
            ws_sbook.append_row(['Booking ID', 'Timestamp', 'User Name', 'Role', 'Space', 'Date', 'Time Slot', 'Recommending Faculty', 'Payment Reference', 'Payment Date', 'Payment Status', 'Booking Status'])

        if "Users" not in existing_tabs:
            ws_users = sh.add_worksheet(title="Users", rows="100", cols="20")
            ws_users.append_row(['User ID', 'Password', 'Role'])
            ws_users.append_row(['admin', hash_password('admin123'), 'Admin'])
            ws_users.append_row(['faculty1', hash_password('fac123'), 'Faculty'])
            ws_users.append_row(['scholar1', hash_password('sch123'), 'Research Scholar'])
            ws_users.append_row(['institute1', hash_password('inst123'), 'Research Institute'])
            ws_users.append_row(['industry1', hash_password('ind123'), 'Industry partner'])
            ws_users.append_row(['incharge1', hash_password('inc123'), 'Instrument Incharge'])
            
    except Exception as e:
        st.error(f"⚠️ Error verifying database structure: {e}")
        
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
# 🧠 SESSION STATE & NATIVE AUTO-LOGIN
# ==========================================
for state in ['logged_in', 'user_role', 'user_name', 'user_category']:
    if state not in st.session_state:
        st.session_state[state] = False if state == 'logged_in' else None

if not st.session_state.logged_in:
    if "user" in st.query_params:
        url_user = st.query_params["user"]
        users_df = get_clean_dataframe("Users")
        if not users_df.empty and 'User ID' in users_df.columns:
            user_match = users_df[users_df['User ID'] == url_user.strip()]
            if not user_match.empty:
                role = user_match.iloc[0]['Role'].strip()
                st.session_state.logged_in = True
                st.session_state.user_role = role
                st.session_state.user_name = url_user.strip()
                
                if role == "Admin": st.session_state.user_category = "System Admin"
                elif role in CU_USERS: st.session_state.user_category = "CU User"
                elif role in NON_CU_USERS: st.session_state.user_category = "Non-CU User"
                elif role in STAFF_USERS: st.session_state.user_category = "Staff"
                else: st.session_state.user_category = "Custom User"

# ==========================================
# 🖼️ GLOBAL HEADER
# ==========================================
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

def render_global_header():
    cu_b64 = get_image_base64("CU_Logo.jpg")
    rusa_b64 = get_image_base64("RUSA_Logo.jpg")
    
    cu_img_html = f'<img src="data:image/jpeg;base64,{cu_b64}" style="width: 100%; max-width: 80px; height: auto;" alt="CU Logo">' if cu_b64 else '<div style="font-size: 10px;">CU Logo Missing</div>'
    rusa_img_html = f'<img src="data:image/jpeg;base64,{rusa_b64}" style="width: 100%; max-width: 80px; height: auto;" alt="RUSA Logo">' if rusa_b64 else '<div style="font-size: 10px;">RUSA Logo Missing</div>'

    header_html = (
        '<div style="display: flex; justify-content: space-between; align-items: center; width: 100%; '
        'padding-bottom: 15px; border-bottom: 2px solid #f0f2f6; margin-bottom: 25px;">'
        f'<div style="flex: 0 0 auto; min-width: 60px;">{cu_img_html}</div>'
        '<div style="flex: 1 1 auto; text-align: center; padding: 0 10px;">'
        '<h2 style="color: #002147; margin: 0; padding: 0; font-size: clamp(1.1rem, 3.5vw, 2.2rem);">University of Calcutta</h2>'
        '<h4 style="margin: 5px 0 0 0; padding: 0; font-size: clamp(0.8rem, 2vw, 1.2rem);">Instrument Booking & Priority Portal</h4>'
        '</div>'
        f'<div style="flex: 0 0 auto; min-width: 60px; text-align: right;">{rusa_img_html}</div>'
        '</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

# ==========================================
# 📝 ATTRIBUTION FOOTER
# ==========================================
def render_footer():
    footer_html = """
    <style>
    .attribution-footer {
        position: fixed;
        bottom: 15px;
        left: 15px;
        font-size: 12px;
        color: #888888;
        z-index: 1000;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 4px 8px;
        border-radius: 4px;
        max-width: 70%;
        line-height: 1.4;
    }
    @media (max-width: 768px) {
        .attribution-footer {
            bottom: 65px; 
            left: 10px;
            font-size: 11px;
            max-width: 85%;
        }
    }
    </style>
    <div class="attribution-footer">
        Concept and development led by Dr. Subhamay Kisku, with associates.
    </div>
    """
    st.markdown(footer_html, unsafe_allow_html=True)

# ==========================================
# 🖥️ LOGIN SYSTEM
# ==========================================
def login_page():
    with st.form("login_form"):
        st.markdown(
            """
            <div style='background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%); padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; box-shadow: 0px 4px 15px rgba(0, 114, 255, 0.3);'>
                <div style='background-color: white; width: 70px; height: 70px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px auto; box-shadow: 0px 4px 10px rgba(0,0,0,0.15);'>
                    <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="#0072ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
                        <polyline points="10 17 15 12 10 7"></polyline>
                        <line x1="15" y1="12" x2="3" y2="12"></line>
                    </svg>
                </div>
                <h3 style='color: white; margin: 0; font-size: 1.8rem; font-weight: 800; letter-spacing: 1px;'>Sign In</h3>
            </div>
            """, 
            unsafe_allow_html=True
        )
        user_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login", use_container_width=True):
            users_df = get_clean_dataframe("Users")
            if not users_df.empty and 'User ID' in users_df.columns:
                users_df['User ID'] = users_df['User ID'].astype(str).str.strip()
                users_df['Password'] = users_df['Password'].astype(str).str.strip()
                hashed_input = hash_password(str(password).strip())
                
                user_match = users_df[(users_df['User ID'] == str(user_id).strip()) & ((users_df['Password'] == hashed_input) | (users_df['Password'] == str(password).strip()))]
                
                if not user_match.empty:
                    role = user_match.iloc[0]['Role'].strip()
                    
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.user_name = user_id.strip()
                    
                    if role == "Admin": st.session_state.user_category = "System Admin"
                    elif role in CU_USERS: st.session_state.user_category = "CU User"
                    elif role in NON_CU_USERS: st.session_state.user_category = "Non-CU User"
                    elif role in STAFF_USERS: st.session_state.user_category = "Staff"
                    else: st.session_state.user_category = "Custom User"
                    
                    st.query_params["user"] = user_id.strip()
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
        
    working_insts = inst_df[~inst_df[status_col_name].isin(['Not Working', 'Maintenance', 'Unavailable'])] if status_col_name else inst_df
    
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
        
        today_ist = datetime.now(IST).date()
        min_allowed_date = today_ist + timedelta(days=3)
        date = st.date_input("Select Date (Min 3 Days Advance)", value=min_allowed_date, min_value=min_allowed_date)
        
        slot = st.selectbox("Select Time Slot", ["10:00 AM - 11:00 AM IST", "11:00 AM - 12:00 PM IST", "02:00 PM - 03:00 PM IST"])
        
        selected_faculty = st.selectbox("Send Recommendation Request To (Faculty)", faculty_list) if is_scholar else None
            
        if st.form_submit_button("Submit Request", type="primary"):
            all_bookings = get_processed_bookings("Bookings", "Instrument Assigned")
            conflict = False
            if not all_bookings.empty and 'Date' in all_bookings.columns:
                existing = all_bookings[(all_bookings['Instrument'] == selected_inst) & (all_bookings['Date'] == str(date)) & (all_bookings['Time Slot'] == slot) & (all_bookings['Booking Status'].isin(['Awaiting Faculty Recommendation', 'Pending Admin Approval', 'Approved, Awaiting Payment', 'Payment Submitted, Awaiting Verification', 'Instrument Assigned']))]
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
                    
                sh.worksheet("Bookings").append_row([booking_id, timestamp, st.session_state.user_name, st.session_state.user_role, selected_inst, str(date), slot, rec_faculty, "N/A", "N/A", "Pending", init_status])
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
        
    working_spaces = space_df[~space_df[status_col_name].isin(['Not Working', 'Maintenance', 'Unavailable'])] if status_col_name else space_df
    
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
        
        today_ist = datetime.now(IST).date()
        min_allowed_date = today_ist + timedelta(days=3)
        date = st.date_input("Select Date (Min 3 Days Advance)", value=min_allowed_date, min_value=min_allowed_date)
        
        slot = st.selectbox("Select Time Slot", ["09:00 AM - 02:00 PM IST (5 Hours)", "02:00 PM - 07:00 PM IST (5 Hours)"])
        
        selected_faculty = st.selectbox("Send Recommendation Request To (Faculty)", faculty_list) if is_scholar else None
            
        if st.form_submit_button("Submit Request", type="primary"):
            all_s_bookings = get_processed_bookings("Space Bookings", "Space Assigned")
            conflict = False
            if not all_s_bookings.empty and 'Date' in all_s_bookings.columns:
                existing = all_s_bookings[(all_s_bookings['Space'] == selected_space) & (all_s_bookings['Date'] == str(date)) & (all_s_bookings['Time Slot'] == slot) & (all_s_bookings['Booking Status'].isin(['Awaiting Faculty Recommendation', 'Pending Admin Approval', 'Approved, Awaiting Payment', 'Payment Submitted, Awaiting Verification', 'Space Assigned']))]
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
                    
                sh.worksheet("Space Bookings").append_row([booking_id, timestamp, st.session_state.user_name, st.session_state.user_role, selected_space, str(date), slot, rec_faculty, "N/A", "N/A", "Pending", init_status])
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
        my_approved = all_bookings[(all_bookings['User Name'] == st.session_state.user_name) & (all_bookings['Booking Status'] == 'Approved, Awaiting Payment')].copy()
        if not my_approved.empty:
            st.dataframe(my_approved[['Booking ID', item_col, 'Date', 'Time Slot', 'Booking Status']], hide_index=True)
            with st.form("payment_submission"):
                target_bkg = st.selectbox("Select Booking ID", my_approved['Booking ID'].tolist())
                pay_ref = st.text_input("Payment Reference Number (Transaction ID)")
                pay_date = st.date_input("Date of Payment", value=datetime.now(IST).date())
                
                if st.form_submit_button("Submit Payment", type="primary"):
                    if not pay_ref:
                        st.error("🚨 Payment Reference Number is required.")
                    else:
                        updates = {"Payment Reference": pay_ref, "Payment Date": str(pay_date), "Booking Status": "Payment Submitted, Awaiting Verification"}
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
    price_map = dict(zip(inst_df['Name'], inst_df.get('Price Rate (₹)', ['0']*len(inst_df)))) if not inst_df.empty and 'Name' in inst_df.columns else {}
        
    if not all_bookings.empty and 'User Name' in all_bookings.columns:
        my_bookings = all_bookings[all_bookings['User Name'] == st.session_state.user_name].copy()
        if not my_bookings.empty:
            my_bookings['Price (₹/hr)'] = my_bookings['Instrument'].map(price_map).fillna("N/A")
            safe_cols = [col for col in ['Date', 'Instrument', 'Price (₹/hr)', 'Time Slot', 'Payment Reference', 'Payment Status', 'Booking Status'] if col in my_bookings.columns]
            st.dataframe(my_bookings[safe_cols].style.apply(highlight_rows, axis=1), hide_index=True, use_container_width=True)
        else:
            st.info("No instrument booking history.")
    else:
        st.info("No instrument booking history.")
        
    st.markdown("---")
    
    # Spaces
    st.markdown("**🏛️ Space / Hall Bookings**")
    all_s_bookings = get_processed_bookings("Space Bookings", "Space Assigned")
    space_df = get_clean_dataframe("Spaces")
    s_price_map = dict(zip(space_df['Name'], space_df.get('Price Rate (₹)', ['0']*len(space_df)))) if not space_df.empty and 'Name' in space_df.columns else {}
        
    if not all_s_bookings.empty and 'User Name' in all_s_bookings.columns:
        my_s_bookings = all_s_bookings[all_s_bookings['User Name'] == st.session_state.user_name].copy()
        if not my_s_bookings.empty:
            my_s_bookings['Price (₹/Slot)'] = my_s_bookings['Space'].map(s_price_map).fillna("N/A")
            s_desired_cols = ['Date', 'Space', 'Price (₹/Slot)', 'Time Slot', 'Payment Reference', 'Payment Status', 'Booking Status']
            s_safe_cols = [col for col in s_desired_cols if col in my_s_bookings.columns]
            st.dataframe(my_s_bookings[s_safe_cols].style.apply(highlight_rows, axis=1), hide_index=True, use_container_width=True)
        else:
            st.info("No space booking history.")
    else:
        st.info("No space booking history.")

# ==========================================
# 🎓 DASHBOARD ROUTING FUNCTIONS
# ==========================================
def standard_user_dashboard():
    st.markdown(
        f"""
        <div style="background-color: #002147; padding: 15px 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; display: flex; align-items: center;">
            <span style="font-size: 1.8rem; margin-right: 12px;">🎓</span>
            <h3 style="margin: 0; color: white; font-size: 1.5rem; font-weight: 600; letter-spacing: 0.5px;">Portal: {st.session_state.user_name} | {st.session_state.user_role} ({st.session_state.user_category})</h3>
        </div>
        """, 
        unsafe_allow_html=True
    )
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Book Instrument", "🏛️ Book Space", "💳 Make Payment", "🔔 My Status"])
    with tab1: render_instrument_booking_form()
    with tab2: render_space_booking_form()
    with tab3: render_payment_form()
    with tab4: render_my_status()

def faculty_dashboard():
    st.markdown(
        f"""
        <div style="background-color: #002147; padding: 15px 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; display: flex; align-items: center;">
            <span style="font-size: 1.8rem; margin-right: 12px;">🧑‍🏫</span>
            <h3 style="margin: 0; color: white; font-size: 1.5rem; font-weight: 600; letter-spacing: 0.5px;">Faculty Portal: {st.session_state.user_name} ({st.session_state.user_category})</h3>
        </div>
        """, 
        unsafe_allow_html=True
    )
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
        price_map = dict(zip(ref_df['Name'], ref_df.get('Price Rate (₹)', ['0']*len(ref_df)))) if not ref_df.empty and 'Name' in ref_df.columns else {}
        
        if not bookings_df.empty and 'Recommending Faculty' in bookings_df.columns:
            pending_reqs = bookings_df[(bookings_df['Recommending Faculty'] == st.session_state.user_name) & (bookings_df['Booking Status'] == 'Awaiting Faculty Recommendation')].copy()
            if not pending_reqs.empty:
                pending_reqs[price_label] = pending_reqs[item_col].map(price_map).fillna("N/A")
                safe_cols = [c for c in ['Booking ID', 'User Name', item_col, price_label, 'Date', 'Time Slot'] if c in pending_reqs.columns]
                st.dataframe(pending_reqs[safe_cols].style.apply(highlight_rows, axis=1), hide_index=True)
                
                with st.form("faculty_review"):
                    target_bkg = st.selectbox("Select Booking ID to Review", pending_reqs['Booking ID'].tolist())
                    decision = st.selectbox("Action", ["Recommend to Admin", "Reject Request"])
                    if st.form_submit_button("Submit Decision", type="primary"):
                        new_status = "Pending Admin Approval" if decision == "Recommend to Admin" else "Rejected by Faculty"
                        if update_record_in_sheet(sheet_target, 0, target_bkg, {"Booking Status": new_status}):
                            st.success(f"✅ {target_bkg} updated to: {new_status}")
                            time.sleep(1)
                            st.rerun()
            else: st.info(f"No pending {req_type.lower()} recommendations.")
        else: st.info("No bookings found in the system.")
            
    with tab2: render_instrument_booking_form()
    with tab3: render_space_booking_form()
    with tab4: render_payment_form()
    with tab5: render_my_status()

def incharge_dashboard():
    st.markdown(
        f"""
        <div style="background-color: #002147; padding: 15px 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; display: flex; align-items: center;">
            <span style="font-size: 1.8rem; margin-right: 12px;">🔧</span>
            <h3 style="margin: 0; color: white; font-size: 1.5rem; font-weight: 600; letter-spacing: 0.5px;">Facility Incharge Portal: {st.session_state.user_name} ({st.session_state.user_category})</h3>
        </div>
        """, 
        unsafe_allow_html=True
    )
    manage_type = st.radio("Select Category to Manage", ["Instruments", "Spaces"])
    if manage_type == "Instruments":
        inst_df = get_clean_dataframe("Instruments")
        if not inst_df.empty:
            id_col = inst_df.columns[0]
            status_col = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
            if status_col:
                st.subheader("Manage Instrument Conditions")
                safe_inst_cols = [c for c in [id_col, 'Name', 'Price Rate (₹)', status_col] if c in inst_df.columns]
                st.dataframe(inst_df[safe_inst_cols].style.apply(highlight_assets, axis=1), hide_index=True, use_container_width=True)
                st.markdown("---")
                with st.form("update_inst_status"):
                    target_inst = st.selectbox("Select Instrument to Update", inst_df[id_col].tolist())
                    new_status = st.selectbox("Update Condition Status", ["Working", "Not Working"])
                    if st.form_submit_button("Apply Status Update", type="primary"):
                        if update_record_in_sheet("Instruments", 0, target_inst, {status_col: new_status}):
                            st.success(f"✅ Instrument {target_inst} successfully marked as {new_status}.")
                            time.sleep(1)
                            st.rerun()
            else: st.error("⚠️ The 'Status' column is missing from your Instruments database.")
        else: st.info("No instruments currently in the database.")
    else:
        space_df = get_clean_dataframe("Spaces")
        if not space_df.empty:
            id_col = space_df.columns[0]
            status_col = next((c for c in space_df.columns if 'status' in str(c).lower()), None)
            if status_col:
                st.subheader("Manage Space Conditions")
                safe_space_cols = [c for c in [id_col, 'Name', 'Capacity', status_col] if c in space_df.columns]
                st.dataframe(space_df[safe_space_cols].style.apply(highlight_assets, axis=1), hide_index=True, use_container_width=True)
                st.markdown("---")
                with st.form("update_space_status"):
                    target_space = st.selectbox("Select Space to Update", space_df[id_col].tolist())
                    new_status = st.selectbox("Update Condition Status", ["Available", "Unavailable", "Maintenance"])
                    if st.form_submit_button("Apply Status Update", type="primary"):
                        if update_record_in_sheet("Spaces", 0, target_space, {status_col: new_status}):
                            st.success(f"✅ Space {target_space} successfully marked as {new_status}.")
                            time.sleep(1)
                            st.rerun()
            else: st.error("⚠️ The 'Status' column is missing from your Spaces database.")
        else: st.info("No spaces currently in the database.")

def admin_dashboard():
    st.markdown(
        """
        <div style="background-color: #002147; padding: 15px 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; display: flex; align-items: center;">
            <span style="font-size: 1.8rem; margin-right: 12px;">🛡️</span>
            <h3 style="margin: 0; color: white; font-size: 1.5rem; font-weight: 600; letter-spacing: 0.5px;">Admin Control Panel</h3>
        </div>
        """, 
        unsafe_allow_html=True
    )
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
        price_map = dict(zip(ref_df['Name'], ref_df.get('Price Rate (₹)', ['0']*len(ref_df)))) if not ref_df.empty and 'Name' in ref_df.columns else {}
            
        if not bookings_df.empty:
            st.subheader(f"Task Queue: {req_type}")
            action_statuses = ["Pending Admin Approval", "Payment Submitted, Awaiting Verification", "Waitlisted"]
            actionable = bookings_df[bookings_df['Booking Status'].isin(action_statuses)].copy()
            if not actionable.empty:
                actionable[price_label] = actionable[item_col].map(price_map).fillna("N/A")
                safe_display_cols = [c for c in ['Booking ID', 'User Name', item_col, price_label, 'Date', 'Time Slot', 'Payment Reference', 'Payment Date', 'Booking Status'] if c in actionable.columns]
                st.dataframe(actionable[safe_display_cols].sort_values(by=['Date']).style.apply(highlight_rows, axis=1), hide_index=True)
            else: st.info("Task Queue is currently empty.")
            
            st.markdown("---")
            st.subheader("Process a Booking")
            with st.form("admin_approval_form"):
                target_bkg = st.selectbox("Select Booking ID", bookings_df['Booking ID'].tolist())
                col1, col2 = st.columns(2)
                with col1: new_payment = st.selectbox("Update Payment Status", ["Pending", "Paid", "Failed/Refunded"])
                with col2: new_status = st.selectbox("Update Booking Status", ["Pending Admin Approval", "Approved, Awaiting Payment", "Payment Submitted, Awaiting Verification", "Waitlisted", "Rejected", assigned_tag, "Completed", "Expired"])
                if st.form_submit_button("Apply Updates", type="primary"):
                    updates = {"Payment Status": new_payment, "Booking Status": new_status}
                    if update_record_in_sheet(sheet_target, 0, target_bkg, updates):
                        st.success(f"✅ Booking {target_bkg} securely updated.")
                        time.sleep(1)
                        st.rerun()
        else: st.info(f"No {req_type.lower()} bookings in system.")

    with tab2:
        st.subheader("Current Instruments Database")
        inst_df = get_clean_dataframe("Instruments")
        if not inst_df.empty:
            status_col_name = next((c for c in inst_df.columns if 'status' in str(c).lower()), None)
            id_col = inst_df.columns[0]
            safe_inst_cols = [c for c in [id_col, 'Name', 'Make / Manufacturer', 'Department / Centre', 'Instrument Incharge', 'Price Rate (₹)', status_col_name] if c in inst_df.columns]
            st.dataframe(inst_df[safe_inst_cols].style.apply(highlight_assets, axis=1), hide_index=True, use_container_width=True)
        else: st.info("No instruments found.")

        st.markdown("---")
        st.subheader("➕ Add New Instrument")
        users_df = get_clean_dataframe("Users")
        incharge_list = users_df[users_df['Role'] == 'Instrument Incharge']['User ID'].tolist() if not users_df.empty and 'Role' in users_df.columns and 'User ID' in users_df.columns else []
            
        with st.form("add_instrument"):
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1: inst_name = st.text_input("Instrument Name*")
            with r1c2: inst_price = st.number_input("Price Rate/hr (₹)*", min_value=0)
            with r1c3: inst_make = st.text_input("Make / Manufacturer")
            
            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1: inst_serial = st.text_input("Serial No.")
            with r2c2: inst_unit = st.text_input("Unit No.")
            with r2c3: inst_campus = st.text_input("Campus Name")
            
            r3c1, r3c2, r3c3 = st.columns(3)
            with r3c1: inst_dept = st.text_input("Department / Centre")
            with r3c2: inst_room = st.text_input("Building / Floor / Room No.")
            with r3c3: 
                if incharge_list: inst_incharge = st.selectbox("Instrument Incharge", ["Select Incharge..."] + incharge_list)
                else: 
                    inst_incharge = st.selectbox("Instrument Incharge", ["No Incharge Found"])
                    st.caption("⚠️ Add an Instrument Incharge user first.")
            
            r4c1, r4c2, r4c3 = st.columns(3)
            with r4c1: inst_desig = st.text_input("Designation of In-charge")
            with r4c2: inst_email = st.text_input("Contact Email")
            with r4c3: st.write("") 
            
            if st.form_submit_button("Add Instrument", type="primary"):
                if inst_name:
                    inst_id = f"INST-{int(datetime.now(IST).timestamp())}"
                    final_incharge = inst_incharge if inst_incharge not in ["Select Incharge...", "No Incharge Found"] else ""
                    sh.worksheet("Instruments").append_row([inst_id, inst_name, inst_make, inst_serial, inst_unit, inst_campus, inst_dept, inst_room, final_incharge, inst_desig, inst_email, inst_price, "Open", "Working"])
                    st.success(f"✅ {inst_name} added to the system.")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()
                else: st.error("Please provide at least an Instrument Name.")

    with tab3:
        st.subheader("Current Spaces & Halls Database")
        space_df = get_clean_dataframe("Spaces")
        if not space_df.empty:
            status_col_name = next((c for c in space_df.columns if 'status' in str(c).lower()), None)
            id_col = space_df.columns[0]
            safe_space_cols = [c for c in [id_col, 'Name', 'Capacity', 'Campus Name', 'Space Incharge', 'Price Rate (₹)', status_col_name] if c in space_df.columns]
            st.dataframe(space_df[safe_space_cols].style.apply(highlight_assets, axis=1), hide_index=True, use_container_width=True)
        else: st.info("No spaces found.")

        st.markdown("---")
        st.subheader("➕ Add New Space / Hall")
        with st.form("add_space"):
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1: space_name = st.text_input("Space / Hall Name*")
            with r1c2: space_price = st.number_input("Price Rate/Slot (₹)*", min_value=0)
            with r1c3: space_campus = st.text_input("Campus Name")
            
            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1: space_room = st.text_input("Building / Floor / Room No.")
            with r2c2: space_capacity = st.number_input("Max Capacity (Persons)", min_value=1, value=50)
            with r2c3: 
                if incharge_list: space_incharge = st.selectbox("Space Incharge", ["Select Incharge..."] + incharge_list)
                else: 
                    space_incharge = st.selectbox("Space Incharge", ["No Incharge Found"])
                    st.caption("⚠️ Add an Instrument Incharge user first.")
            
            r3c1, r3c2, r3c3 = st.columns(3)
            with r3c1: space_email = st.text_input("Contact Email")
            with r3c2: st.write("") 
            with r3c3: st.write("") 
            
            if st.form_submit_button("Add Space", type="primary"):
                if space_name:
                    space_id = f"SPC-{int(datetime.now(IST).timestamp())}"
                    final_space_incharge = space_incharge if space_incharge not in ["Select Incharge...", "No Incharge Found"] else ""
                    sh.worksheet("Spaces").append_row([space_id, space_name, space_campus, space_room, space_capacity, final_space_incharge, space_email, space_price, "Available"])
                    st.success(f"✅ {space_name} added to the system.")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()
                else: st.error("Please provide at least a Space Name.")

    with tab4:
        users_df = get_clean_dataframe("Users")
        if not users_df.empty:
            display_users = users_df.copy()
            if 'Password' in display_users.columns: display_users['Password'] = '******'
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
                existing = pd.DataFrame(sh.worksheet("Users").get_all_records())
                if not existing.empty and str(new_uid).strip() in existing['User ID'].astype(str).str.strip().tolist(): st.error("🚨 User ID already exists.")
                elif not new_uid or not new_pass: st.error("🚨 ID and Password required.")
                elif not final_role: st.error("🚨 Role name cannot be empty.")
                else:
                    sh.worksheet("Users").append_row([new_uid.strip(), hash_password(new_pass.strip()), final_role])
                    st.success(f"🎉 {new_uid} added as {final_role}!")
                    get_clean_dataframe.clear()
                    time.sleep(1)
                    st.rerun()

# ==========================================
# 🚀 ROOT APPLICATION EXECUTION
# ==========================================
render_global_header()

if not st.session_state.logged_in:
    login_page()
else:
    # 🚪 NATIVE LOGOUT BUTTON
    col1, col2 = st.columns([9, 1])
    with col2:
        st.markdown('<div id="logout_marker"></div>', unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True):
            st.query_params.clear()
            for key in ['logged_in', 'user_role', 'user_name', 'user_category']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
            
    # Load correct dashboard
    if st.session_state.user_role == "Admin": admin_dashboard()
    elif st.session_state.user_role == "Faculty": faculty_dashboard()
    elif st.session_state.user_role == "Instrument Incharge": incharge_dashboard()
    else: standard_user_dashboard()
        
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    
    col_s1, col_s2, col_s3 = st.columns([4, 2, 4])
    with col_s2:
        st.markdown('<div id="sync_marker"></div>', unsafe_allow_html=True)
        if st.button("🔄 Sync Application Data", use_container_width=True):
            get_clean_dataframe.clear()
            st.rerun()

render_footer()
