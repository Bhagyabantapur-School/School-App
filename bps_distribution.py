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

# Initialize Session State for Login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = ""

# ==========================================
# 2. GOOGLE SHEETS CONNECTION
# ==========================================
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(credentials)

gc = get_gspread_client()

# Fetch Student Data from BPS_Database
@st.cache_data(ttl=600)
def load_student_master():
    try:
        db_sheet = gc.open("BPS_Database")
        ws_students = db_sheet.worksheet("students_master")
        return pd.DataFrame(ws_students.get_all_records())
    except Exception as e:
        st.error(f"Error loading students_master: {e}")
        return pd.DataFrame()

# ==========================================
# 3. LOGIN SCREEN
# ==========================================
# ==========================================
# 3. LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("logo.png"):
            image = Image.open("logo.png")
            st.image(image, width=80)
        else:
            st.write("🏫")
    with col2:
        st.title("Bhagyabantapur Primary School")
        st.subheader("Staff Login")

    # --- NEW: App Description and Purpose ---
    st.info("""
    **Welcome to the Digital Supply Distribution Portal!**
    
    **Purpose:** This application is designed to streamline and digitize the distribution of school supplies (Books, Uniforms, and Bags). 
    
    **Key Features:**
    * 📦 **Real-time Tracking:** Replaces manual paper logs with instant digital records.
    * 🔒 **Secure Audit Trail:** Every issued item is permanently timestamped and linked to the distributing teacher.
    * 📊 **Instant Summaries:** Provides the administration with live, up-to-date distribution metrics.
    """)
    st.markdown("<br>", unsafe_allow_html=True) # A little spacing before the login box
    # ----------------------------------------

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Log In")

        if submit_button:
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                # Store the user's actual name instead of their login ID
                st.session_state.current_user = USERS[username]["name"] 
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid Username or Password")
                
    st.markdown("<br><br><p style='text-align: center; color: gray; font-size: 14px;'>Developed by Sukhamay Kisku (H.M.)</p>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 4. MAIN APPLICATION (LOGGED IN)
# ==========================================
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if os.path.exists("logo.png"):
        image = Image.open("logo.png")
        st.image(image, width=80)
with col2:
    st.title("BPS Distribution")
with col3:
    st.info(f"👤 **{st.session_state.current_user}**")
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.current_user = ""
        st.rerun()

st.markdown("---")

# Load Data
df_students = load_student_master()
if df_students.empty:
    st.warning("No student data found in 'students_master' tab of 'BPS_Database'.")
    st.stop()

# Set up tabs
tab_entry, tab_summary = st.tabs(["Distribute Items", "My Session Summary"])

# --- TEACHER ENTRY TAB ---
with tab_entry:
    st.header("Issue Supplies to Students")
    
    distribution_type = st.radio("Select Item Category Being Distributed:", ["Books", "Uniform", "Bag"], horizontal=True)
    
    if 'current_distribution' not in st.session_state:
        st.session_state.current_distribution = {}

    classes = df_students['Class'].unique()
    
    for cls in classes:
        st.subheader(f"CLASS {cls}")
        class_df = df_students[df_students['Class'] == cls]
        
        for index, row in class_df.iterrows():
            widget_key = f"{cls}_{row['Roll']}_{row['Name']}"
            
            if widget_key not in st.session_state.current_distribution:
                st.session_state.current_distribution[widget_key] = False
                
            is_checked = st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=f"chk_{widget_key}")
            st.session_state.current_distribution[widget_key] = is_checked

        st.markdown("---")

    if st.button(f"Submit {distribution_type} Distribution to Database", type="primary"):
        with st.spinner("Saving logs to Google Sheets..."):
            try:
                log_sheet = gc.open("BPS_Distribution_Log")
                log_ws = log_sheet.sheet1 
                
                now = datetime.now()
                current_date = now.strftime("%Y-%m-%d")
                current_time = now.strftime("%H:%M:%S")
                teacher = st.session_state.current_user
                
                rows_to_append = []
                
                for cls in classes:
                    class_df = df_students[df_students['Class'] == cls]
                    for index, row in class_df.iterrows():
                        widget_key = f"{cls}_{row['Roll']}_{row['Name']}"
                        
                        if st.session_state.current_distribution.get(widget_key, False):
                            books_given, uniform_given, bag_given = False, False, False
                            if distribution_type == "Books": books_given = True
                            if distribution_type == "Uniform": uniform_given = True
                            if distribution_type == "Bag": bag_given = True
                            
                            log_row = [
                                current_date, 
                                current_time, 
                                teacher, 
                                cls, 
                                row['Roll'], 
                                row['Name'], 
                                books_given, 
                                uniform_given, 
                                bag_given
                            ]
                            rows_to_append.append(log_row)
                
                if rows_to_append:
                    log_ws.append_rows(rows_to_append)
                    st.success(f"Successfully logged {len(rows_to_append)} distributions!")
                    
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
        df_logs = pd.DataFrame(st.session_state.recent_logs, columns=['Date', 'Time', 'Teacher', 'Class', 'Roll', 'Name', 'Books', 'Uniform', 'Bag'])
        st.dataframe(df_logs, hide_index=True)
    else:
        st.write("No distributions logged yet in this session.")

# ==========================================
# 5. FOOTER
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True) # Adds some breathing room at the bottom
st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>Developed by Sukhamay Kisku (H.M.)</p>", unsafe_allow_html=True)
