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

# Dummy user database for the login system (Replace with your actual teachers/passwords)
USER_CREDENTIALS = {
    "admin": "admin123",
    "teacher_pp": "pp123",
    "teacher_lpp": "lpp123"
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
@st.cache_data(ttl=600) # Caches data for 10 minutes to speed up the app
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
if not st.session_state.logged_in:
    # Display Logo and Title on Login Page
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("logo.png"):
            image = Image.open("logo.png")
            st.image(image, width=80)
        else:
            st.write("🏫") # Fallback if logo.png is missing
    with col2:
        st.title("Bhagyabantapur Primary School")
        st.subheader("Staff Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Log In")

        if submit_button:
            if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid Username or Password")
    st.stop() # Stops the rest of the code from running if not logged in

# ==========================================
# 4. MAIN APPLICATION (LOGGED IN)
# ==========================================
# Header with Logo, School Name, and User Info
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
    
    # Create a local dictionary to store checkbox states before submitting
    if 'current_distribution' not in st.session_state:
        st.session_state.current_distribution = {}

    # Separate classes
    classes = df_students['Class'].unique()
    
    for cls in classes:
        st.subheader(f"CLASS {cls}")
        class_df = df_students[df_students['Class'] == cls]
        
        for index, row in class_df.iterrows():
            # Unique key for every checkbox
            widget_key = f"{cls}_{row['Roll']}_{row['Name']}"
            
            # Default to False
            if widget_key not in st.session_state.current_distribution:
                st.session_state.current_distribution[widget_key] = False
                
            # Checkbox UI
            is_checked = st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=f"chk_{widget_key}")
            st.session_state.current_distribution[widget_key] = is_checked

        st.markdown("---")

    # Submit Button Logic
    if st.button(f"Submit {distribution_type} Distribution to Database", type="primary"):
        with st.spinner("Saving logs to Google Sheets..."):
            try:
                # Open the Log Sheet
                log_sheet = gc.open("BPS_Distribution_Log")
                log_ws = log_sheet.sheet1 
                
                # Prepare data rows to append
                now = datetime.now()
                current_date = now.strftime("%Y-%m-%d")
                current_time = now.strftime("%H:%M:%S")
                teacher = st.session_state.current_user
                
                rows_to_append = []
                
                for cls in classes:
                    class_df = df_students[df_students['Class'] == cls]
                    for index, row in class_df.iterrows():
                        widget_key = f"{cls}_{row['Roll']}_{row['Name']}"
                        
                        # Only log the students who actually received the item just now
                        if st.session_state.current_distribution.get(widget_key, False):
                            # Default flags
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
                    # Append all new rows at once to the bottom of the log sheet
                    log_ws.append_rows(rows_to_append)
                    st.success(f"Successfully logged {len(rows_to_append)} distributions!")
                    
                    # Store locally for the summary tab
                    if 'recent_logs' not in st.session_state:
                        st.session_state.recent_logs = []
                    st.session_state.recent_logs.extend(rows_to_append)
                    
                    # Uncheck all boxes after successful submit
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
