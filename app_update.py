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

# --- 2. CONNECT TO THE SHEET (BYPASSING DRIVE API ERROR) ---
# IMPORTANT: Replace the string below with the EXACT full URL of your "APP UPDATE" Google Sheet
# It should look something like: "https://docs.google.com/spreadsheets/d/1A2b3C4d5E.../edit"
SHEET_URL = "PASTE_YOUR_GOOGLE_SHEET_URL_HERE" 

try:
    # Use open_by_url to completely bypass the Google Drive API search
    sheet = client.open_by_url(SHEET_URL)
    
    # Connect to the "Update" tab based on your CSV structure
    worksheet = sheet.worksheet("Update") 
    
except gspread.exceptions.APIError as e:
    st.error(f"API Error. Ensure the Service Account email is added as an 'Editor' to the Sheet. Details: {e}")
    st.stop()
except Exception as e:
    st.error(f"Could not connect to the Sheet or Tab. Please check the URL and tab name. Details: {e}")
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
        # Convert all inputs to strings/formats that Google Sheets can accept
        row_data = [
            str(date_input),
            str(time_input.strftime("%H:%M:%S")), # Clean time formatting
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
            # append_row automatically adds the array to the next available empty row
            worksheet.append_row(row_data)
            st.success("Successfully logged the update to the 'APP UPDATE' Google Sheet!")
        except Exception as e:
            st.error(f"An error occurred while saving: {e}")
