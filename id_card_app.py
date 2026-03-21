import streamlit as st
import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

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

# --- 3. HELPER FUNCTIONS ---
@st.cache_data(ttl=60) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

def make_drive_image_url(url):
    """Converts a standard Drive share link into a direct-view link for Streamlit."""
    if pd.isna(url) or not isinstance(url, str) or "drive.google.com" not in url:
        return url
    # Extract file ID and convert to direct link format
    if "/d/" in url:
        file_id = url.split("/d/")[1].split("/")[0]
        return f"https://drive.google.com/uc?id={file_id}"
    return url

def update_photo_status_in_cloud(student_name, roll, student_class):
    try:
        log_ws = sh.worksheet("photo_log")
        log_ws.append_row([datetime.now().strftime("%d-%m-%Y"), student_class, roll, student_name, "Taken"])
        st.cache_data.clear()
    except:
        st.error("Cloud update failed. Ensure 'photo_log' sheet exists.")

# --- 4. APP LAYOUT ---
tabs = st.tabs(["🖨️ ID Generator", "📂 Database Explorer"])

# ==========================================
# TAB 1: ID GENERATOR (Strict Filter)
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
        df_master['Roll'] = df_master['Roll'].astype(str)
        df_log['Roll'] = df_log['Roll'].astype(str)
        merged = pd.merge(df_master, df_log, on=['Class', 'Section', 'Roll'], how='inner')
        
        def is_ready_to_print(row):
            has_photo = pd.notna(row.get('Photo_URL')) and str(row.get('Photo_URL')).strip() != ""
            is_returned = str(row.get('Return Status', '')).strip() == 'Complete'
            has_corr = any([str(row.get(f'Old {f}', '')).strip() not in ['','nan','None'] for f in ['Student Name', 'Father Name']])
            is_verified = str(row.get('Data Corrected', '')).strip() == 'Yes'
            return has_photo and is_returned and (is_verified if has_corr else True)

        merged['Ready'] = merged.apply(is_ready_to_print, axis=1)
        print_ready = merged[merged['Ready'] == True].copy()

        if not print_ready.empty:
            print_ready.insert(0, "Select", False)
            st.data_editor(
                print_ready[['Select', 'Roll', 'Name', 'Class', 'Section']],
                hide_index=True, use_container_width=True, key="gen_editor"
            )
        else:
            st.info("No students found with a linked Photo URL and a cleared form.")

# ==========================================
# TAB 2: DATABASE EXPLORER (With Thumbnails)
# ==========================================
with tabs[1]:
    st.subheader("📂 Student Database & Media Tracker")
    
    df_m = fetch_sheet_data("students_master")
    df_l = fetch_sheet_data("form_distribution_log")
    df_m['Roll'] = df_m['Roll'].astype(str)
    df_l['Roll'] = df_l['Roll'].astype(str)
    
    explorer_db = pd.merge(df_m, df_l, on=['Class', 'Section', 'Roll'], how='left')
    
    # 1. Prepare Thumbnail Links for Streamlit
    if 'Thumb_URL' in explorer_db.columns:
        explorer_db['Display_Thumb'] = explorer_db['Thumb_URL'].apply(make_drive_image_url)
    else:
        explorer_db['Display_Thumb'] = None

    # 2. Status Flags
    explorer_db['Photo_Link'] = explorer_db['Photo_URL'].apply(lambda x: True if pd.notna(x) and "drive" in str(x) else False)
    explorer_db['Form_OK'] = explorer_db['Return Status'].apply(lambda x: True if str(x) == "Complete" else False)
    explorer_db['Verified'] = explorer_db['Data Corrected'].apply(lambda x: True if str(x) == "Yes" else False)
    explorer_db['Photo Taken'] = False 

    # 3. Filter UI
    cat_filter = st.selectbox("Filter Students:", ["All Students", "Missing Photo Link", "Form Pending"])
    
    filtered_view = explorer_db.copy()
    if cat_filter == "Missing Photo Link":
        filtered_view = filtered_view[filtered_view['Photo_Link'] == False]
    elif cat_filter == "Form Pending":
        filtered_view = filtered_view[filtered_view['Form_OK'] == False]

    # 4. The Data Grid
    st.write("---")
    final_ed = st.data_editor(
        filtered_view[['Photo Taken', 'Display_Thumb', 'Name', 'Class', 'Roll', 'Photo_Link', 'Form_OK', 'Verified']],
        column_config={
            "Photo Taken": st.column_config.CheckboxColumn("Photo Taken"),
            "Display_Thumb": st.column_config.ImageColumn("Thumbnail", width="small"),
            "Photo_Link": st.column_config.CheckboxColumn("Link OK?", disabled=True),
            "Form_OK": st.column_config.CheckboxColumn("Form OK?", disabled=True),
            "Verified": st.column_config.CheckboxColumn("Verified?", disabled=True),
        },
        disabled=['Display_Thumb', 'Name', 'Class', 'Roll', 'Photo_Link', 'Form_OK', 'Verified'],
        hide_index=True,
        use_container_width=True,
        key="db_explorer_grid"
    )

    if st.button("💾 Sync Manual Photo Status"):
        taken_list = final_ed[final_ed['Photo Taken'] == True]
        if not taken_list.empty:
            for _, row in taken_list.iterrows():
                update_photo_status_in_cloud(row['Name'], row['Roll'], row['Class'])
            st.success("Synced to Cloud!")
            st.rerun()
