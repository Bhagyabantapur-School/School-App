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

def get_sheet_and_maxes(client, sheet_name="value_distributor", tab_name="value_distributor"):
    """Opens the sheet, fetches the max values from the headers, and returns the worksheet."""
    if not client: 
        return None, [0, 0, 0, 0]
    
    try:
        sh = client.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Could not find the Google Sheet named '{sheet_name}'.")
        return None, [0, 0, 0, 0]

    try:
        worksheet = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Could not find the tab named '{tab_name}'.")
        return None, [0, 0, 0, 0]

    # Fetch the first row (headers)
    headers = worksheet.row_values(1)
    
    # Extract maxes from columns C, D, E, F (which are indices 2, 3, 4, 5)
    maxes = []
    for i in range(2, 6):
        if i < len(headers):
            try:
                # Convert the header text to an integer
                maxes.append(int(str(headers[i]).strip()))
            except ValueError:
                # Fallback to 0 if the cell isn't a valid number
                maxes.append(0) 
        else:
            maxes.append(0)
            
    return worksheet, maxes

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

# --- INIT CLIENT AND FETCH MAXES ---
client = init_gsheets()
worksheet, maxes = get_sheet_and_maxes(client)

# --- USER INTERFACE ---
st.title("Value Distributor")

if sum(maxes) > 0:
    st.info(f"**Max limits synced from Google Sheets:** {maxes[0]} | {maxes[1]} | {maxes[2]} | {maxes[3]}")
else:
    st.warning("Could not read valid maximum numbers from columns C, D, E, and F in your Google Sheet.")

st.subheader("Distribute Value")

# Using a form to allow rapid entry via the "Enter" key
with st.form("entry_form", clear_on_submit=True):
    # value=None keeps the input blank by default
    total_val = st.number_input("Total Value to Distribute", min_value=0, step=1, value=None)
    submitted = st.form_submit_button("Distribute & Add")

    if submitted:
        if total_val is None:
            st.error("Please enter a valid total value.")
        else:
            distribution = distribute(total_val, maxes)
            
            if distribution is None:
                st.error("Error: Total exceeds the sum of the header maximums!")
            else:
                row_data = [st.session_state.sl_no, total_val] + distribution
                st.session_state.data_entries.append(row_data)
                
                # Sync to Google Sheets automatically
                if worksheet:
                    worksheet.append_row(row_data)
                
                st.session_state.sl_no += 1
                st.success("Distributed successfully and synced to Sheets!")

st.subheader("Distribution Results")
if st.session_state.data_entries:
    df = pd.DataFrame(
        st.session_state.data_entries, 
        columns=["Sl.No.", "Total Given", f"Max: {maxes[0]}", f"Max: {maxes[1]}", f"Max: {maxes[2]}", f"Max: {maxes[3]}"]
    )
    
    # Apply styling to highlight 0 values
    def highlight_zero(row):
        if row["Total Given"] == 0:
            return ['background-color: #fff3cd; color: #856404; font-weight: bold'] * len(row)
        return [''] * len(row)
        
    st.dataframe(df.style.apply(highlight_zero, axis=1), use_container_width=True)
else:
    st.info("No entries yet.")
