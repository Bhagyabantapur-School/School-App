import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from PIL import Image
import os

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
st.set_page_config(page_title="BPS Supply Distribution", page_icon="🏫", layout="centered")

# Actual Staff Database 
USERS = {
    "admin": {"name": "SUKHAMAY KISKU", "role": "admin", "password": "bpsAPP@2026"}, 
    "tr": {"name": "TAPASI RANA", "role": "teacher", "password": "tr26"}, 
    "sbr": {"name": "SUJATA BISWAS ROTHA", "role": "teacher", "password": "sbr26"}, 
    "rs": {"name": "ROHINI SINGH", "role": "teacher", "password": "rs26"}, 
    "unj": {"name": "UDAY NARAYAN JANA", "role": "teacher", "password": "unj26"}, 
    "bkp": {"name": "BIMAL KUMAR PATRA", "role": "teacher", "password": "bkp26"}, 
    "sp": {"name": "SUSMITA PAUL", "role": "teacher", "password": "sp26"}, 
    "tkm": {"name": "TAPAN KUMAR MANDAL", "role": "teacher", "password": "tkm26"}, 
    "mk": {"name": "MANJUMA KHATUN", "role": "teacher", "password": "mk26"}
}

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = ""
if 'current_role' not in st.session_state:
    st.session_state.current_role = ""

# ==========================================
# 2. GOOGLE SHEETS CONNECTION & DATA LOADING
# ==========================================
@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(credentials)

gc = get_gspread_client()

@st.cache_data(ttl=600)
def load_gsheet_data(sheet_name, tab_name):
    """Generic function to load a specific tab from a specific Google Sheet"""
    try:
        ws = gc.open(sheet_name).worksheet(tab_name)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"Error loading {tab_name} from {sheet_name}: {e}")
        return pd.DataFrame()

def get_active_items():
    """Fetches the admin-selected items from the settings tab in BPS_Distribution_Log"""
    df_settings = load_gsheet_data("BPS_Distribution_Log", "settings")
    if not df_settings.empty and 'Setting_Name' in df_settings.columns:
        active_row = df_settings[df_settings['Setting_Name'] == 'Active_Items']
        if not active_row.empty:
            items_str = active_row.iloc[0]['Value']
            return [item.strip() for item in items_str.split(',') if item.strip()]
    return ["Books", "Uniform", "Bag"] # Fallback

# ==========================================
# 3. LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("logo.png"):
            st.image(Image.open("logo.png"), width=80)
        else:
            st.write("🏫")
    with col2:
        st.title("Bhagyabantapur Primary School")
        st.subheader("Staff Login")

    st.info("""
    **Welcome to the Digital Supply Distribution Portal!**
    
    **Purpose:** Streamline the distribution of school supplies directly to students present today.
    
    **Key Features:**
    * 📦 **Admin Controls:** Headmaster selects which items are active for distribution.
    * 🔗 **Live MDM Sync:** Only displays students marked 'Present' in the BPS Digital App today.
    * 🔒 **Secure Audit Trail:** Every issued item is permanently timestamped.
    """)
    st.markdown("<br>", unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Log In")

        if submit_button:
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.current_user = USERS[username]["name"]
                st.session_state.current_role = USERS[username]["role"]
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid Username or Password")
                
    st.markdown("<br><br><p style='text-align: center; color: gray; font-size: 14px;'>Developed by Sukhamay Kisku (H.M.)</p>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 4. MAIN APPLICATION 
# ==========================================
# Header
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if os.path.exists("logo.png"):
        st.image(Image.open("logo.png"), width=80)
with col2:
    st.title("BPS Distribution")
with col3:
    st.info(f"👤 **{st.session_state.current_user}**\n\n({st.session_state.current_role.title()})")
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.current_user = ""
        st.session_state.current_role = ""
        st.rerun()

st.markdown("---")

if st.session_state.current_role == "admin":
    tab_entry, tab_summary, tab_admin = st.tabs(["Distribute Items", "My Session Summary", "⚙️ Admin Settings"])
else:
    tab_entry, tab_summary = st.tabs(["Distribute Items", "My Session Summary"])

# --- TEACHER ENTRY TAB ---
with tab_entry:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.header("Issue Supplies")
    with col_b:
        if st.button("🔄 Sync Live Data"):
            st.cache_data.clear()
            st.rerun()

    # Load Data from their respective sheets
    df_students = load_gsheet_data("BPS_Database", "students_master")
    df_mdm = load_gsheet_data("BPS_Database", "mdm_log")
    active_items = get_active_items()

    if df_students.empty:
        st.warning("No student data found in students_master.")
        st.stop()
        
    st.info("⚠️ Only showing students who are present in the BPS Digital App today.")

    if not active_items:
        st.error("No items currently authorized for distribution. Please contact the Admin.")
    else:
        distribution_type = st.selectbox("Select Item Category Being Distributed:", active_items)
        
        col1, col2 = st.columns(2)
        with col1:
            classes = sorted(df_students['Class'].astype(str).unique())
            sel_class = st.selectbox("Select Class", classes)
        with col2:
            available_sections = sorted(df_students[df_students['Class'].astype(str) == sel_class]['Section'].astype(str).unique())
            sel_section = st.selectbox("Select Section", available_sections)

        st.markdown("---")
        
        # Filtering logic for Present Students Today
        # NOTE: Ensure the Date format below matches how your MDM App writes to the sheet!
        today_str = datetime.now().strftime("%Y-%m-%d") 
        
        if not df_mdm.empty and 'Date' in df_mdm.columns:
            # Since there is no 'Status' column, we assume presence if they have an entry today
            mdm_today = df_mdm[df_mdm['Date'].astype(str) == today_str]
            
            mdm_filtered = mdm_today[(mdm_today['Class'].astype(str) == sel_class) & 
                                     (mdm_today['Section'].astype(str) == sel_section)]
            
            present_rolls = mdm_filtered['Roll'].astype(str).tolist()
            
            class_df = df_students[(df_students['Class'].astype(str) == sel_class) & 
                                   (df_students['Section'].astype(str) == sel_section) &
                                   (df_students['Roll'].astype(str).isin(present_rolls))]
        else:
            class_df = pd.DataFrame() 

        if class_df.empty:
            st.warning(f"No students found logged in the MDM App today for Class {sel_class} - Section {sel_section}.")
        else:
            st.subheader(f"Present Students: Class {sel_class} ({sel_section})")
            
            if 'current_distribution' not in st.session_state:
                st.session_state.current_distribution = {}

            for index, row in class_df.iterrows():
                widget_key = f"{sel_class}_{sel_section}_{row['Roll']}_{row['Name']}"
                
                if widget_key not in st.session_state.current_distribution:
                    st.session_state.current_distribution[widget_key] = False
                    
                is_checked = st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=f"chk_{widget_key}")
                st.session_state.current_distribution[widget_key] = is_checked

            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button(f"Submit {distribution_type} Distribution", type="primary"):
                with st.spinner("Saving logs to Google Sheets..."):
                    try:
                        log_sheet = gc.open("BPS_Distribution_Log")
                        log_ws = log_sheet.sheet1 
                        
                        now = datetime.now()
                        current_date = now.strftime("%Y-%m-%d")
                        current_time = now.strftime("%H:%M:%S")
                        teacher = st.session_state.current_user
                        
                        rows_to_append = []
                        
                        for index, row in class_df.iterrows():
                            widget_key = f"{sel_class}_{sel_section}_{row['Roll']}_{row['Name']}"
                            
                            if st.session_state.current_distribution.get(widget_key, False):
                                log_row = [
                                    current_date, 
                                    current_time, 
                                    teacher, 
                                    sel_class, 
                                    sel_section,
                                    row['Roll'], 
                                    row['Name'], 
                                    distribution_type 
                                ]
                                rows_to_append.append(log_row)
                        
                        if rows_to_append:
                            log_ws.append_rows(rows_to_append)
                            st.success(f"Successfully logged {len(rows_to_append)} {distribution_type}(s)!")
                            
                            if 'recent_logs' not in st.session_state:
                                st.session_state.recent_logs = []
                            st.session_state.recent_logs.extend(rows_to_append)
                            
                            st.session_state.current_distribution.clear()
                            st.rerun()
                        else:
                            st.warning("No students were selected. Nothing was saved.")
                            
                    except Exception as e:
                        st.error(f"Failed to save to Google Sheets: {e}")

# --- SUMMARY TAB ---
with tab_summary:
    st.header("Your Recent Submissions")
    st.info("This shows the distributions you have logged during this current login session.")
    
    if 'recent_logs' in st.session_state and st.session_state.recent_logs:
        df_logs = pd.DataFrame(st.session_state.recent_logs, columns=['Date', 'Time', 'Teacher', 'Class', 'Section', 'Roll', 'Name', 'Item Given'])
        st.dataframe(df_logs, hide_index=True)
    else:
        st.write("No distributions logged yet in this session.")

# --- ADMIN SETTINGS TAB ---
if st.session_state.current_role == "admin":
    with tab_admin:
        st.header("Distribution Configuration")
        st.write("Select which items teachers are allowed to distribute today.")
        
        master_item_list = ["Books", "Uniform", "Bag", "Shoes", "Sweater", "Stationery"]
        current_active = get_active_items()
        
        for item in current_active:
            if item not in master_item_list:
                master_item_list.append(item)
                
        new_active_items = st.multiselect("Active Distribution Items:", master_item_list, default=current_active)
        
        if st.button("Save Settings", type="primary"):
            try:
                ws_settings = gc.open("BPS_Distribution_Log").worksheet("settings")
                items_to_save = ", ".join(new_active_items)
                
                cell = ws_settings.find("Active_Items")
                if cell:
                    ws_settings.update_cell(cell.row, cell.col + 1, items_to_save)
                    st.success("Settings saved successfully! Teachers will now see these options.")
                    st.cache_data.clear() 
                else:
                    st.error("Could not find 'Active_Items' row in the settings tab. Make sure A2 says exactly 'Active_Items'.")
            except Exception as e:
                st.error(f"Error saving settings: {e}")

# ==========================================
# 5. FOOTER
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>Developed by Sukhamay Kisku (H.M.)</p>", unsafe_allow_html=True)
