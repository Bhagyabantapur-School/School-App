import streamlit as st
import pandas as pd
import qrcode
import os
import math
from fpdf import FPDF
import tempfile
from datetime import datetime

# --- IMPORTS FOR GOOGLE SHEETS & DRIVE API ---
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from google.auth.transport.requests import AuthorizedSession

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS Digital - ID Generator", page_icon="🏫", layout="wide")

# --- 2. GOOGLE CONNECTION ---
@st.cache_resource
def get_google_credentials():
    skey = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    return Credentials.from_service_account_info(skey, scopes=scopes)

@st.cache_resource
def init_gsheets():
    try:
        creds = get_google_credentials()
        gc = gspread.authorize(creds)
        return gc.open("BPS_Database")
    except Exception as e:
        st.error("⚠️ Google Sheets Connection Failed!")
        st.stop()

sh = init_gsheets()

# --- 3. DATA PERSISTENCE FUNCTIONS ---
@st.cache_data(ttl=60) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

def update_photo_status_in_cloud(student_name, roll, student_class):
    """Updates the database when a teacher confirms a photo is taken."""
    try:
        ws = sh.worksheet("students_master")
        cell = ws.find(student_name) # Simplification: in production use a Unique ID
        # Logic to update a 'Photo_Status' column if you have one, 
        # or logging into a separate 'photo_log' sheet
        log_ws = sh.worksheet("photo_log")
        log_ws.append_row([datetime.now().strftime("%d-%m-%Y"), student_class, roll, student_name, "Taken"])
        st.cache_data.clear()
    except:
        st.error("Cloud update failed.")

# --- 4. APP LAYOUT ---
tabs = st.tabs(["🖨️ ID Generator", "📸 Scanner", "📂 Database Explorer"])

# ==========================================
# TAB 1: GENERATOR (Filtered by Photo_URL)
# ==========================================
with tabs[0]:
    h_col1, h_col2 = st.columns([1, 5])
    with h_col1:
        if os.path.exists('logo.png'): st.image('logo.png', width=70)
    with h_col2:
        st.markdown("<h2 style='margin-top:10px;'>BPS Student ID Card Generator</h2>", unsafe_allow_html=True)
    
    st.divider()

    df_master = fetch_sheet_data("students_master")
    df_log = fetch_sheet_data("form_distribution_log")
    
    if not df_master.empty and not df_log.empty:
        # Merge data
        df_master['Roll'] = df_master['Roll'].astype(str)
        df_log['Roll'] = df_log['Roll'].astype(str)
        merged = pd.merge(df_master, df_log, on=['Class', 'Section', 'Roll'], how='inner')
        
        # CRITERIA: Must have Photo_URL AND meet Form Return criteria
        def is_ready_to_print(row):
            has_photo = pd.notna(row.get('Photo_URL')) and str(row.get('Photo_URL')).strip() != ""
            is_returned = str(row.get('Return Status', '')).strip() == 'Complete'
            # Check for corrections
            has_corr = any([str(row.get(f'Old {f}', '')).strip() not in ['','nan','None'] for f in ['Student Name', 'Father Name']])
            is_corr_done = str(row.get('Data Corrected', '')).strip() == 'Yes'
            
            return has_photo and is_returned and (is_corr_done if has_corr else True)

        merged['Ready'] = merged.apply(is_ready_to_print, axis=1)
        print_list = merged[merged['Ready'] == True].copy()

        if not print_list.empty:
            print_list.insert(0, "Select", False)
            st.write("### Students Ready for Printing")
            st.caption("Only students with linked Photo URLs and completed forms appear here.")
            
            ed_df = st.data_editor(
                print_list[['Select', 'Roll', 'Name', 'Class', 'Section']],
                hide_index=True, use_container_width=True, key="print_editor"
            )
        else:
            st.info("No students found with both a Photo URL and a completed form.")

# ==========================================
# TAB 3: DATABASE EXPLORER (Interactive)
# ==========================================
with tabs[2]:
    st.subheader("📊 Photo & Form Verification Tracker")
    
    df_m = fetch_sheet_data("students_master")
    df_l = fetch_sheet_data("form_distribution_log")
    df_m['Roll'] = df_m['Roll'].astype(str)
    df_l['Roll'] = df_l['Roll'].astype(str)
    
    explorer_db = pd.merge(df_m, df_l, on=['Class', 'Section', 'Roll'], how='left')
    
    # Logic for columns
    explorer_db['Photo_URL_Exists'] = explorer_db['Photo_URL'].apply(lambda x: True if pd.notna(x) and "drive" in str(x) else False)
    explorer_db['Form_Returned'] = explorer_db['Return Status'].apply(lambda x: True if str(x) == "Complete" else False)
    explorer_db['Data_Verified'] = explorer_db['Data Corrected'].apply(lambda x: True if str(x) == "Yes" else False)
    
    # Checkbox for "Photo Taken" (Interactive)
    # We use a helper column to see if it's already in the cloud log
    explorer_db['Photo Taken'] = False 

    # Filter Dropdown
    mode = st.selectbox("View Category:", ["All Students", "Missing Photo Link", "Form Pending"])
    
    filt_df = explorer_db.copy()
    if mode == "Missing Photo Link": filt_df = filt_df[filt_df['Photo_URL_Exists'] == False]
    elif mode == "Form Pending": filt_df = filt_df[filt_df['Form_Returned'] == False]

    # Data Editor with requested columns
    st.write("#### Data Grid")
    st.caption("Click 'Photo Taken' to mark progress. Once checked and saved, it syncs to cloud.")
    
    tracked_df = st.data_editor(
        filt_df[['Photo Taken', 'Name', 'Class', 'Roll', 'Photo_URL_Exists', 'Form_Returned', 'Data_Verified']],
        column_config={
            "Photo Taken": st.column_config.CheckboxColumn("Photo Taken", help="Mark if physical photo session is done"),
            "Photo_URL_Exists": st.column_config.CheckboxColumn("Photo Link?", disabled=True),
            "Form_Returned": st.column_config.CheckboxColumn("Form Back?", disabled=True),
            "Data_Verified": st.column_config.CheckboxColumn("Verified?", disabled=True),
        },
        disabled=['Name', 'Class', 'Roll', 'Photo_URL_Exists', 'Form_Returned', 'Data_Verified'],
        hide_index=True,
        use_container_width=True,
        key="explorer_editor"
    )

    if st.button("Sync Status to Cloud"):
        newly_taken = tracked_df[tracked_df['Photo Taken'] == True]
        if not newly_taken.empty:
            for _, row in newly_taken.iterrows():
                update_photo_status_in_cloud(row['Name'], row['Roll'], row['Class'])
            st.success(f"Synced {len(newly_taken)} updates to BPS_Database!")
            st.rerun()
