
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import time

# --- 1. SETUP & AUTHENTICATION (Using st.secrets) ---

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Pull credentials directly from Streamlit Secrets
creds_dict = dict(st.secrets["gcp_service_account"])
creds = ServiceAccountCredentials.from_service_account_info(creds_dict, scope)
client = gspread.authorize(creds)

# Connect to the databases
sheet_project = client.open("BPS YTfb Videos").worksheet("Logs")
sheet_master = client.open("MY ROUTINE 2026").worksheet("activity_log")

# --- 2. ARCHITECTURE FUNCTIONS ---

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try:
        sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
    except TypeError:
        sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

@st.cache_data
def get_master_log():
    return sheet_master.get_all_records()

@st.cache_data
def get_project_log():
    return sheet_project.get_all_records()

# --- 3. STOP TASK UI & DUAL-LOGGING LOGIC ---

st.divider()
st.subheader("⏹ Stop Active Phase & Log")

# (Assuming UI logic identifies the active task here)
# Example variables based on the active task:
active_row_number = 15 # The row in MY ROUTINE 2026 where End_Time is "RUNNING"
start_time_recorded = "14:30:00"

st.info("Currently Running: Video Editing (Annual Sports Day)")

if st.button("Stop & Log", type="primary"):
    
    now = get_ist_time()
    end_time_log = now.strftime("%H:%M:%S") 
    
    with st.spinner("Writing to dual databases..."):
        try:
            # --- DATABASE 1: MY ROUTINE 2026 ---
            # Headers: Date(1), Start_Time(2), End_Time(3), Duration(4), Activity(5), Sub_Activities(6)...
            # We target Column 3 (End_Time) and Column 4 (Duration)
            
            # Master Formula mapping to Column B (Start) and Column C (End)
            gs_formula_master = f'=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm:ss"), ""))'
            
            sheet_master.update_cell(active_row_number, 3, end_time_log)
            sheet_master.update_cell(active_row_number, 4, gs_formula_master)

            # --- DATABASE 2: BPS YTfb Videos ---
            # Project Formula mapping to Column F (Start) and Column G (End)
            gs_formula_project = f'=IF(INDIRECT("G"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("G"&ROW())-INDIRECT("F"&ROW()), 1), "h:mm:ss"), ""))'
            
            row_data = [
                now.strftime("%Y-%m-%d"), # A: Log Date
                "Annual Sports Day",      # B: Event Name
                "Editing",                # C: Video Phase
                "DJI Pocket",             # D: Recording Device
                "Filmora",                # E: Editing Tool
                start_time_recorded,      # F: Start Time
                end_time_log,             # G: End Time
                gs_formula_project        # H: Duration Formula
            ]
            
            smart_append_row(sheet_project, row_data)

            # --- CLEAR CACHE & RERUN ---
            get_master_log.clear()
            get_project_log.clear()
            
            st.success("Task successfully logged to both databases!")
            time.sleep(1.0)
            st.rerun()

        except Exception as e:
            st.error(f"An error occurred during logging: {e}")
