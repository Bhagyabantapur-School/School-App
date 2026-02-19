import streamlit as st
import pandas as pd
import qrcode
import os
from fpdf import FPDF
import tempfile
import json
import io

# --- GOOGLE DRIVE API IMPORTS ---
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS ID Card Generator", page_icon="🪪", layout="centered")

# --- 2. STYLING ---
st.markdown("""
    <style>
        .main-header { font-size: 30px; font-weight: bold; color: #007bff; text-align: center; }
        .sub-header { font-size: 18px; color: #555; text-align: center; margin-bottom: 20px; }
        .stButton>button { width: 100%; background-color: #28a745; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 3. GOOGLE DRIVE HELPER FUNCTIONS ---
@st.cache_resource
def get_drive_service():
    """Authenticates and returns the Google Drive Service using Streamlit Secrets."""
    try:
        # Load the JSON string you pasted into Streamlit Secrets
        creds_json = json.loads(st.secrets["gcp_credentials"])
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_json, scopes=scopes)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        return None

def get_all_drive_photos(service, folder_id):
    """Fetches a list of all photos currently saved in your Drive folder."""
    if not service: return {}
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)", pageSize=1000).execute()
    # Returns a dictionary like: {'BPS_Photo_1_12.jpg': 'drive_file_id_here'}
    return {item['name']: item['id'] for item in results.get('files', [])}

def upload_to_drive(service, folder_id, file_name, file_bytes, existing_file_id=None):
    """Uploads a new photo or overwrites an existing one in Google Drive."""
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='image/jpeg', resumable=True)
    if existing_file_id:
        # Update existing file
        service.files().update(fileId=existing_file_id, media_body=media).execute()
    else:
        # Create new file
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        service.files().create(body=file_metadata, media_body=media).execute()

def download_from_drive(service, file_id, local_path):
    """Downloads a photo from Drive to a temporary local file for the PDF."""
    request = service.files().get_media(fileId=file_id)
    with open(local_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

# --- 4. DATA HELPER FUNCTIONS ---
@st.cache_data
def get_students():
    if os.path.exists('students.csv'):
        try:
            df = pd.read_csv('students.csv')
            if 'Class' in df.columns:
                df['Class'] = df['Class'].replace('CALSS IV', 'CLASS IV')
            for col in ['Section', 'BloodGroup', 'Father', 'Gender', 'DOB', 'Mobile']:
                if col not in df.columns:
                    df[col] = 'N/A'
            return df
        except Exception as e:
            st.error(f"Error loading CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def generate_pdf(students_list, drive_service, drive_folder_id, drive_files_map):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    x_start, y_start = 10, 10
    card_w, card_h = 86, 54
    gap = 8
    col, row = 0, 0
    
    for student in students_list:
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # 1. Card Border
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, card_w, card_h)
        
        # 2. Header
        pdf.set_fill_color(0, 123, 255)
        pdf.rect(x, y, card_w, 11, 'F')
        
        if os.path.exists('logo.png'):
            pdf.image('logo.png', x=x + 2, y=y + 1.5, w=8, h=8)
            
        pdf.set_font("Arial", 'B', 8.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x + 10, y + 1.5)
        pdf.cell(card_w - 10, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x + 10, y + 6.5)
        pdf.cell(card_w - 10, 3, "ID CARD - SESSION 2026", 0, 1, 'C')
        
        pdf.set_text_color(0, 0, 0)
        
        # 3. Photo Fetching Logic
        photo_x, photo_y, photo_w, photo_h = x + 3, y + 14, 18, 22
        student_id = student.get('Sl', 0)
        student_roll = student.get('Roll', '0')
        expected_photo_name = f"BPS_Photo_{student_id}_{student_roll}.jpg"
        
        photo_downloaded = False
        if drive_service and expected_photo_name in drive_files_map:
            # Download the photo from Google Drive just for this PDF
            temp_path = tempfile.mktemp(suffix=".jpg")
            try:
                download_from_drive(drive_service, drive_files_map[expected_photo_name], temp_path)
                pdf.image(temp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
                pdf.set_draw_color(0, 0, 0)
                pdf.rect(photo_x, photo_y, photo_w, photo_h)
                photo_downloaded = True
            except:
                pass

        if not photo_downloaded:
            # Draw placeholder if no photo is in Drive
            pdf.set_draw_color(200, 200, 200)
            pdf.rect(photo_x, photo_y, photo_w, photo_h) 
            pdf.set_text_color(150, 150, 150)
            pdf.set_font("Arial", '', 5)
            pdf.set_xy(photo_x, photo_y + 8)
            pdf.cell(photo_w, 5, "NO", 0, 1, 'C')
            pdf.set_xy(photo_x, photo_y + 11)
            pdf.cell(photo_w, 5, "PHOTO", 0, 0, 'C')
        
        # 4. Student Details
        pdf.set_text_color(0, 0, 0)
        detail_x = x + 24
        curr_y = y + 14
        line_h = 4
        
        pdf.set_font("Arial", 'B', 9)
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"{student.get('Name', '')}".upper()[:25], 0, 1)
        curr_y += 4.5

        pdf.set_font("Arial", '', 7)
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Father: {student.get('Father', 'N/A')}", 0, 1)
        curr_y += line_h
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Class: {student.get('Class', '')} | Sec: {student.get('Section', 'A')}", 0, 1)
        curr_y += line_h
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Roll: {student.get('Roll', '')} | Sex: {student.get('Gender', 'N/A')}", 0, 1)
        curr_y += line_h
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"DOB: {student.get('DOB', 'N/A')} | Blood: {student.get('BloodGroup', 'N/A')}", 0, 1)
        curr_y += line_h
        pdf.set_xy(detail_x, curr_y)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(50, line_h, f"Mob: {student.get('Mobile', 'N/A')}", 0, 1)
        
        # 5. QR Code (Left aligned under photo)
        qr_data = f"Name:{student.get('Name', '')}|Roll:{student.get('Roll', '')}|Mob:{student.get('Mobile', '')}"
        qr = qrcode.make(qr_data)
        qr_path = tempfile.mktemp(suffix=".png")
        qr.save(qr_path)
        pdf.image(qr_path, x=x + 4.5, y=y + 37, w=15, h=15)
        
        # 6. Signature Area (Right aligned)
        if os.path.exists('signature.png'):
            pdf.image('signature.png', x=x + 58, y=y + 41, w=22, h=8)
            
        pdf.set_font("Arial", 'I', 6)
        pdf.set_xy(x, y + 49)
        pdf.cell(card_w - 5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5)
        pdf.set_xy(x, y + 51)
        pdf.cell(card_w - 5, 2, "Head Teacher", 0, 0, 'R')
        
        col += 1
        if col >= 2:
            col, row = 0, row + 1
        if row >= 5:
            pdf.add_page()
            col, row = 0, 0
            
    return pdf.output(dest='S').encode('latin-1')

# --- 5. APP INIT & CLOUD CHECK ---
drive_service = get_drive_service()
drive_folder_id = st.secrets.get("drive_folder_id", "")
drive_files_map = get_all_drive_photos(drive_service, drive_folder_id) if drive_service else {}

# --- 6. APP LAYOUT ---
col_a, col_b, col_c = st.columns([1, 2, 1])
with col_b:
    if os.path.exists('logo.png'):
        st.image('logo.png', use_container_width=True)

st.markdown('<p class="main-header">🪪 BPS Student ID Card Generator</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Cloud-Synced Photo Database</p>', unsafe_allow_html=True)

if not drive_service:
    st.warning("⚠️ Google Drive is not connected. Photos will not be saved permanently. Check Streamlit Secrets.")

df = get_students()

if not df.empty:
    col1, col2 = st.columns(2)
    with col1:
        classes = ["All"] + sorted(df['Class'].dropna().unique().tolist())
        selected_class = st.selectbox("Filter by Class", classes)
    with col2:
        sections = ["All"] + sorted(df['Section'].dropna().unique().tolist())
        selected_section = st.selectbox("Filter by Section", sections)

    filtered_df = df.copy()
    if selected_class != "All": filtered_df = filtered_df[filtered_df['Class'] == selected_class]
    if selected_section != "All": filtered_df = filtered_df[filtered_df['Section'] == selected_section]
        
    st.divider()
    
    st.write(f"Found **{len(filtered_df)}** students. Select students to manage or print.")
    filtered_df.insert(0, "Select", False)
    disabled_cols = filtered_df.columns.drop(["Select", "BloodGroup"])
    
    edited_df = st.data_editor(
        filtered_df,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(required=True),
            "BloodGroup": st.column_config.SelectboxColumn("Blood Group", options=["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "N/A"])
        },
        disabled=disabled_cols,
        use_container_width=True
    )
    
    selected_students = edited_df[edited_df["Select"] == True].copy()
    
    st.divider()
    
    # --- CLOUD PHOTO UPLOAD SECTION ---
    if not selected_students.empty:
        st.markdown('### ☁️ Manage Cloud Photos')
        
        for index, student in selected_students.iterrows():
            student_id = student.get('Sl', index)
            student_roll = student.get('Roll', '0')
            photo_name = f"BPS_Photo_{student_id}_{student_roll}.jpg"
            
            # Check if photo already exists in Google Drive
            has_cloud_photo = photo_name in drive_files_map
            status_icon = "✅" if has_cloud_photo else "📷"
            
            with st.expander(f"{status_icon} Photo: {student.get('Name', 'Unknown')} (Class: {student.get('Class', '')}, Roll: {student_roll})"):
                
                if has_cloud_photo:
                    st.success("Photo is securely saved in Google Drive!")
                
                photo = st.file_uploader(
                    "Upload New Photo to Drive" if has_cloud_photo else "Choose Image", 
                    type=['jpg', 'jpeg', 'png'], 
                    key=f"photo_{student_id}_{student_roll}"
                )
                
                if photo is not None and drive_service:
                    with st.spinner("Uploading to Google Drive..."):
                        file_bytes = photo.getvalue()
                        existing_id = drive_files_map.get(photo_name)
                        upload_to_drive(drive_service, drive_folder_id, photo_name, file_bytes, existing_id)
                        
                        # Refresh map so it shows success instantly
                        drive_files_map = get_all_drive_photos(drive_service, drive_folder_id)
                        st.success("Successfully synced to Google Drive!")
                        st.image(photo, width=150)

    st.divider()
    
    # --- GENERATION BUTTONS ---
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Select All in Filtered List"):
            st.info("Tip: Click the checkbox at the very top of the 'Select' column in the table to select all.")

    with c2:
        if not selected_students.empty:
            if st.button(f"🖨️ Fetch Photos & Generate PDF for {len(selected_students)} Students"):
                with st.spinner("Syncing photos from Drive and building PDF... (this may take a minute)"):
                    student_data = selected_students.to_dict('records')
                    pdf_bytes = generate_pdf(student_data, drive_service, drive_folder_id, drive_files_map)
                    
                    st.download_button(
                        label="📥 Download Ready! Click to Save PDF",
                        data=pdf_bytes,
                        file_name="bps_id_cards.pdf",
                        mime="application/pdf"
                    )
        else:
            st.warning("Please select at least one student from the table above.")

else:
    st.error("❌ 'students.csv' file not found.")
