import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pytz
from datetime import datetime

# --- 1. AUTHENTICATION SETUP ---
# Define the Google Sheets API scope
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Fetch the credentials from Streamlit Secrets
# dict() converts the TOML section into a Python dictionary format expected by Google
try:
    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )
    # Authorize the gspread client
    client = gspread.authorize(credentials)
except Exception as e:
    st.error(f"Authentication failed. Please check your Streamlit Secrets. Error: {e}")
    st.stop()

# --- 2. CONNECT TO THE SHEET ---
# Replace this with the exact name of your Google Sheet
SHEET_NAME = "App_Update_Log" 

try:
    sheet = client.open(SHEET_NAME)
    # Connect to the specific tab that matches your CSV file
    worksheet = sheet.worksheet("Update") 
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"Could not find a Google Sheet named '{SHEET_NAME}'. Make sure you shared it with the service account email.")
    st.stop()
except gspread.exceptions.WorksheetNotFound:
    st.error("Could not find a tab named 'Update' in the sheet.")
    st.stop()

# --- 3. TIMEZONE CONFIGURATION ---
# Get current time in Indian Standard Time (IST)
ist = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(ist)

# --- 4. STREAMLIT USER INTERFACE ---
st.title("BPS Digital - App Update Logger")
st.write("Submit new app update details directly to the Google Sheet.")

# Create a form to input the data matching your CSV structure
with st.form("update_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        # Pre-populate with current IST date and time
        date_input = st.date_input("Date", value=current_ist.date())
        time_input = st.time_input("Time", value=current_ist.time())
        app_input = st.text_input("App Name")
        details_input = st.text_area("Details of Update")
        ai_input = st.text_input("AI Used (e.g., Gemini)")
        
    with col2:
        short_input = st.text_input("Short Description")
        lines_input = st.number_input("Lines of Code", min_value=0, step=1)
        features_input = st.text_input("Features Added")
        selected_ai = st.selectbox("Selected from AI?", ["Yes", "No"])
        chat_input = st.text_input("Chat Reference / Link")

    submitted = st.form_submit_button("Save to Google Sheet")

    # --- 5. APPEND DATA LOGIC ---
    if submitted:
        # Convert date and time to strings so Google Sheets can process them
        row_data = [
            str(date_input),
            str(time_input.strftime("%H:%M:%S")), # Format time cleanly
            app_input,
            details_input,
            ai_input,
            short_input,
            lines_input,
            features_input,
            selected_ai,
            chat_input
        ]
        
        try:
            # append_row automatically adds the data to the next available empty row
            worksheet.append_row(row_data)
            st.success("Successfully logged the update to the Google Sheet!")
        except Exception as e:
            st.error(f"An error occurred while saving: {e}")
