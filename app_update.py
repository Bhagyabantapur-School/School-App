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

# --- 2. CONNECT TO THE SHEET BY NAME ---
SHEET_NAME = "APP UPDATE" 

try:
    sheet = client.open(SHEET_NAME)
    worksheet = sheet.worksheet("Update") 
except gspread.exceptions.APIError as e:
    st.error(f"API Error. Ensure the 'Google Drive API' is enabled in your Google Cloud Project, and the Service Account is an Editor on the Sheet. Details: {e}")
    st.stop()
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"Could not find a Google Sheet named '{SHEET_NAME}'. Make sure you shared it with the service account email.")
    st.stop()
except gspread.exceptions.WorksheetNotFound:
    st.error("Could not find a tab named 'Update' in the sheet.")
    st.stop()

# --- 3. TIMEZONE CONFIGURATION ---
ist = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(ist)

# --- 4. STREAMLIT USER INTERFACE ---
st.title("BPS Digital - App Update Logger")
st.write("Submit new app update details directly to the Google Sheet.")

with st.form("update_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        date_input = st.date_input("Date", value=current_ist.date())
        # Added step=60 for 1-minute granularity
        time_input = st.time_input("Time", value=current_ist.time(), step=60)
        
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

    submitted = st.form_submit_button("Save to Google Sheet")

    # --- 5. APPEND DATA LOGIC ---
    if submitted:
        row_data = [
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
            worksheet.append_row(row_data)
            st.success("Successfully logged the update to the 'APP UPDATE' Google Sheet!")
        except Exception as e:
            st.error(f"An error occurred while saving: {e}")
