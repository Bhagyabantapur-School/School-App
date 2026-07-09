import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pytz
from datetime import datetime

# --- 1. AUTHENTICATION SETUP ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
except Exception as e:
    st.error(f"Authentication failed. Please check your Streamlit Secrets. Error: {e}")
    st.stop()

# --- 2. CONNECT TO THE SHEET & WORKSHEETS ---
SHEET_NAME = "APP UPDATE" 

try:
    sheet = client.open(SHEET_NAME)
    
    # Connect to both tabs in your Google Sheet
    worksheet_update = sheet.worksheet("Update") 
    worksheet_common = sheet.worksheet("Common")
    
except gspread.exceptions.APIError as e:
    st.error(f"API Error. Ensure the 'Google Drive API' is enabled in your Google Cloud Project, and the Service Account is an Editor on the Sheet. Details: {e}")
    st.stop()
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"Could not find a Google Sheet named '{SHEET_NAME}'. Make sure you shared it with the service account email.")
    st.stop()
except gspread.exceptions.WorksheetNotFound as e:
    st.error(f"Could not find a required tab in the sheet. Ensure you have both 'Update' and 'Common' tabs. Details: {e}")
    st.stop()

# --- 3. TIMEZONE CONFIGURATION ---
ist = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(ist)

# --- 4. STREAMLIT USER INTERFACE ---
st.title("BPS Digital - App & Feature Logger")
st.write("Submit new app updates or log reusable common features directly to the Google Sheet.")

# Create the two-tab layout
tab1, tab2 = st.tabs(["🚀 Log App Update", "🧩 Log Common Feature"])

# ==========================================
# TAB 1: THE APP UPDATE LOGGER (11 Columns)
# ==========================================
with tab1:
    with st.form("update_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Added unique keys to prevent widget ID conflicts across tabs
            date_input = st.date_input("Date", value=current_ist.date(), key="date_update")
            time_input = st.time_input("Time", value=current_ist.time(), step=60, key="time_update") 
            
            app_input = st.text_input("App Name")
            details_input = st.text_area("Details of Update")
            ai_input = st.text_input("AI Used (e.g., Gemini)")
            ai_answer = st.text_area("AI Answer")
            
        with col2:
            short_input = st.text_input("Short Description")
            lines_input = st.number_input("Lines of Code", min_value=0, step=1)
            features_input = st.text_input("Features Added")
            selected_ai = st.text_area("Selected AI Content (Paste the line here)")
            chat_input = st.text_input("Chat Reference / Link")

        submitted_update = st.form_submit_button("Save Update to Google Sheet")

        if submitted_update:
            row_data_update = [
                str(date_input),
                str(time_input.strftime("%H:%M:%S")),
                app_input,
                details_input,
                ai_input,
                ai_answer,       
                short_input,     
                lines_input,
                features_input,
                selected_ai,     
                chat_input
            ]
            
            try:
                worksheet_update.append_row(row_data_update)
                st.success("Successfully logged the update to the 'Update' tab!")
            except Exception as e:
                st.error(f"An error occurred while saving: {e}")

# ==========================================
# TAB 2: THE COMMON FEATURE LOGGER (7 Columns)
# ==========================================
with tab2:
    with st.form("common_form", clear_on_submit=True):
        col3, col4 = st.columns(2)
        
        with col3:
            date_input_common = st.date_input("Date", value=current_ist.date(), key="date_common")
            time_input_common = st.time_input("Time", value=current_ist.time(), step=60, key="time_common") 
            
            common_feature = st.text_input("Common Feature Name")
            prompt_input = st.text_area("Prompt (of the app feature)")
            
        with col4:
            used_in_app = st.text_input("Used in App (Where it was first used)")
            chat_input_common = st.text_input("Chat Name")
            use_in_other = st.text_area("Use in other app (Add names as you use this in the future)")

        submitted_common = st.form_submit_button("Save Feature to Google Sheet")

        if submitted_common:
            row_data_common = [
                str(date_input_common),
                str(time_input_common.strftime("%H:%M:%S")),
                common_feature,
                prompt_input,
                used_in_app,
                chat_input_common,
                use_in_other
            ]
            
            try:
                worksheet_common.append_row(row_data_common)
                st.success("Successfully logged the feature to the 'Common' tab!")
            except Exception as e:
                st.error(f"An error occurred while saving: {e}")
