import streamlit as st
import pandas as pd
import base64
import re
import os
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
import datetime
from fpdf import FPDF

# --- 1. SECURE GOOGLE CONNECTION ---
@st.cache_resource
def get_google_credentials():
    skey = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    return Credentials.from_service_account_info(skey, scopes=scopes)

@st.cache_resource
def init_gsheets():
    creds = get_google_credentials()
    gc = gspread.authorize(creds)
    return gc.open("BPS_Database")

@st.cache_resource
def get_drive_session():
    creds = get_google_credentials()
    return AuthorizedSession(creds)

sh = init_gsheets()

# --- 2. DATABASE HELPER FUNCTIONS ---
@st.cache_data(ttl=5) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df = df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
        return df
    except:
        return pd.DataFrame()

def clear_sheet_cache():
    fetch_sheet_data.clear()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: 
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    
    df = df.fillna("").astype(str)
    ws.append_rows(df.values.tolist())
    clear_sheet_cache()

# --- 3. SECURE IMAGE FETCHING ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        authed_session = get_drive_session()
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        response = authed_session.get(url)
        if response.status_code == 200: return response.content
        return None
    except Exception: return None

def get_secure_photo_uri(url):
    fallback_image = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str): return fallback_image

    file_id = None
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match: file_id = match.group(1)

    if file_id:
        image_bytes = fetch_secure_image_bytes(file_id)
        if image_bytes:
            b64_str = base64.b64encode(image_bytes).decode()
            return f"data:image/jpeg;base64,{b64_str}"
            
    return url if url.startswith("http") else fallback_image

# --- START NEW APP UI BELOW ---

st.set_page_config(page_title="BPS Birthdays", page_icon="🎂")

st.title("🎂 BPS Birthday Manager")

# Strict Mobile Responsiveness CSS for Flexbox
st.markdown("""
<style>
@media (max-width: 768px) {
    [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        overflow-x: hidden !important;
    }
}
</style>
""", unsafe_allow_html=True)

# 1. Fetch Data with API Rate Limit Safety
with st.spinner("Syncing with BPS Database..."):
    try:
        df_students = fetch_sheet_data("students_master")
        df_teachers = fetch_sheet_data("TEACHERS_DETAIL")
    except APIError:
        st.error("Google Sheets API Quota Exceeded. Please try again later.")
        st.stop()
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        st.stop()

if df_students.empty and df_teachers.empty:
    st.warning("No data found in BPS_Database.")
    st.stop()

# 2. Process Data to Standardized Format
records = []

# Process Students Data
if not df_students.empty:
    for idx, row in df_students.iterrows():
        dob_str = str(row.get('DOB', '')).strip()
        name = str(row.get('Name', '')).strip()
        cls = str(row.get('Class', '')).strip().upper()
        sec = str(row.get('Section', '')).strip().upper()
        
        # Rule: Treat CLASS PP and LPP as a combined unit
        if cls in ["CLASS PP", "CLASS LPP"]:
            cls = "CLASS PP & LPP"
            
        if dob_str and name and dob_str != "nan":
            try:
                dt = pd.to_datetime(dob_str, errors='coerce')
                if pd.notna(dt):
                    records.append({
                        'Name': name,
                        'Category': f"{cls} - Section {sec}" if sec else cls,
                        'Role': 'Student',
                        'Month_Num': dt.month,
                        'Month_Name': dt.strftime('%B'),
                        'Day': dt.day,
                        'DOB_Formatted': dt.strftime('%d-%b-%Y')
                    })
            except Exception:
                pass

# Process Teachers Data
if not df_teachers.empty:
    for idx, row in df_teachers.iterrows():
        dob_str = str(row.get('DOB', '')).strip()
        name = str(row.get('Name', '')).strip()
        designation = str(row.get('Designation', 'Staff')).strip()
        
        if dob_str and name and dob_str != "nan":
            try:
                # Assuming Indian format DD-MM-YYYY for manual teacher inputs
                dt = pd.to_datetime(dob_str, dayfirst=True, errors='coerce')
                if pd.notna(dt):
                    records.append({
                        'Name': f"{name} ({designation})",
                        'Category': "Staff & Teachers", 
                        'Role': 'Teacher',
                        'Month_Num': dt.month,
                        'Month_Name': dt.strftime('%B'),
                        'Day': dt.day,
                        'DOB_Formatted': dt.strftime('%d-%b-%Y')
                    })
            except Exception:
                pass

df_bday = pd.DataFrame(records)

if df_bday.empty:
    st.info("No valid dates of birth found in the database.")
    st.stop()

# 3. UI Filtering
st.markdown("### Filter Options")
months = ["All Months"] + [datetime.date(2000, m, 1).strftime('%B') for m in range(1, 13)]
selected_month = st.selectbox("Select Month to Display", months)

if selected_month != "All Months":
    filtered_df = df_bday[df_bday['Month_Name'] == selected_month].copy()
else:
    filtered_df = df_bday.copy()

# Sort by Day of Month internally
filtered_df = filtered_df.sort_values(by=['Month_Num', 'Day'])

# CUSTOM SORTING: Force "CLASS PP & LPP" to the very top
all_categories = sorted(filtered_df['Category'].unique())
pp_categories = [cat for cat in all_categories if "CLASS PP & LPP" in cat]
other_categories = [cat for cat in all_categories if cat not in pp_categories]
final_category_order = pp_categories + other_categories


# 4. PDF Generation Logic (Modern fpdf2 standard)
def generate_birthday_pdf(dataframe, month_title, category_order):
    pdf = FPDF()
    pdf.add_page()
    
    # Add Logo if it exists
    if os.path.exists("logo.png"):
        pdf.image("logo.png", x=12, y=8, w=18)
    
    # Header Title
    pdf.set_font("helvetica", "B", 16)
    pdf.set_y(10)
    pdf.cell(0, 8, f"Bhagyabantapur Primary School", new_x="LMARGIN", new_y="NEXT", align="C")
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, f"Birthday Roster: {month_title}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(8) 
    
    # Overall Serial Number Counter for PDF
    overall_sl = 1 
    
    for cat in category_order:
        group = dataframe[dataframe['Category'] == cat]
        if group.empty: continue
        
        # Dynamic Teacher Labeling
        display_cat = cat
        if cat == "Staff & Teachers":
            display_cat = "Teachers" if len(group) > 1 else "Teacher"
            
        # Category Header
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(41, 128, 185) # BPS Blueish
        pdf.cell(0, 8, f"[{display_cat}]", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        
        # Apply continuous serial numbers
        for _, row in group.iterrows():
            bday_text = f" {overall_sl:02d}. {row['Name']} (DOB: {row['DOB_Formatted']})"
            pdf.cell(0, 6, bday_text, new_x="LMARGIN", new_y="NEXT")
            overall_sl += 1 # Increment overall counter
        pdf.ln(4)
        
    return bytes(pdf.output())


# 5. Display List & Export
if filtered_df.empty:
    st.info(f"No birthdays recorded in {selected_month}.")
else:
    # Render PDF Download Button
    pdf_bytes = generate_birthday_pdf(filtered_df, selected_month, final_category_order)
    
    col_dl, col_space = st.columns([1, 2])
    with col_dl:
        st.download_button(
            label="📄 Export to PDF",
            data=pdf_bytes,
            file_name=f"BPS_Birthdays_{selected_month.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
    
    st.divider()
    
    # Overall Serial Number Counter for UI
    overall_sl_ui = 1 
    
    # Render UI Visuals following custom layout order
    for cat in final_category_order:
        group = filtered_df[filtered_df['Category'] == cat]
        if group.empty: continue
        
        display_cat = cat
        if cat == "Staff & Teachers":
            display_cat = "Teachers" if len(group) > 1 else "Teacher"
            
        st.markdown(f"#### 🏷️ {display_cat}")
        
        # Removed columns to prevent any horizontal scrolling on small mobile screens
        for _, row in group.iterrows():
            st.markdown(f"**{overall_sl_ui:02d}.** {row['Name']} *(DOB: {row['DOB_Formatted']})*")
            overall_sl_ui += 1 # Increment overall counter
            
        st.write("") # Spacer
