import streamlit as st
import pandas as pd
import random
import math
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Value Distributor", layout="wide")

# --- GOOGLE SHEETS SETUP ---
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_resource
def init_gsheets():
    """Initialize the Google Sheets client using Streamlit secrets."""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Authentication failed: Check your Streamlit Secrets. Error: {e}")
        return None

def setup_and_update_sheet(client, row_data, sheet_name="value_distributor", tab_name="Distributions"):
    """Opens the existing sheet, creates the tab if it doesn't exist, then appends the data."""
    if not client: return
    
    # 1. Open your existing Spreadsheet
    try:
        # Opens the sheet you manually created and shared
        sh = client.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Could not find the Google Sheet named '{sheet_name}'. Ensure your service account email is added as an Editor!")
        return

    # 2. Handle Tab Creation
    try:
        worksheet = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=tab_name, rows="1000", cols="6")
        worksheet.append_row(["Sl.No.", "Total Given", "Part 1", "Part 2", "Part 3", "Part 4"])
        st.toast(f"New tab '{tab_name}' created!")

    # 3. Append the new row
    worksheet.append_row(row_data)

# --- DISTRIBUTION LOGIC ---
def distribute(total, maxes):
    if total > sum(maxes) or total < 0:
        return None
    
    result = [0, 0, 0, 0]
    remaining = total
    
    while remaining > 0:
        valid_indices = [i for i in range(4) if result[i] < maxes[i]]
        random.shuffle(valid_indices)
        i = valid_indices[0]
        
        max_possible_chunk = min(
            remaining, 
            maxes[i] - result[i], 
            max(1, math.ceil(remaining / len(valid_indices)))
        )
        chunk = random.randint(1, max_possible_chunk)
        
        result[i] += chunk
        remaining -= chunk
        
    return result

# --- SESSION STATE INITIALIZATION ---
if "data_entries" not in st.session_state:
    st.session_state.data_entries = []
if "sl_no" not in st.session_state:
    st.session_state.sl_no = 1

# --- USER INTERFACE ---
st.title("Value Distributor")

st.subheader("1. Set Maximum Header Values")
col1, col2, col3, col4 = st.columns(4)
with col1: max1 = st.number_input("Header 1 Max", min_value=0, value=10)
with col2: max2 = st.number_input("Header 2 Max", min_value=0, value=10)
with col3: max3 = st.number_input("Header 3 Max", min_value=0, value=10)
with col4: max4 = st.number_input("Header 4 Max", min_value=0, value=10)

maxes = [max1, max2, max3, max4]

st.subheader("2. Distribute Value")
# Using a form to allow rapid entry via the "Enter" key
with st.form("entry_form", clear_on_submit=True):
    total_val = st.number_input("Total Value to Distribute", min_value=0, step=1)
    submitted = st.form_submit_button("Distribute & Add")

    if submitted:
        distribution = distribute(total_val, maxes)
        
        if distribution is None:
            st.error("Error: Total exceeds the sum of the header maximums!")
        else:
            row_data = [st.session_state.sl_no, total_val] + distribution
            st.session_state.data_entries.append(row_data)
            
            # Sync to Google Sheets automatically
            client = init_gsheets()
            if client:
                setup_and_update_sheet(client, row_data)
            
            st.session_state.sl_no += 1
            st.success("Distributed successfully and synced to Sheets!")

st.subheader("Distribution Results")
if st.session_state.data_entries:
    df = pd.DataFrame(
        st.session_state.data_entries, 
        columns=["Sl.No.", "Total Given", "Part 1", "Part 2", "Part 3", "Part 4"]
    )
    
    # Apply styling to highlight 0 values
    def highlight_zero(row):
        if row["Total Given"] == 0:
            return ['background-color: #fff3cd; color: #856404; font-weight: bold'] * len(row)
        return [''] * len(row)
        
    st.dataframe(df.style.apply(highlight_zero, axis=1), use_container_width=True)
else:
    st.info("No entries yet.")
