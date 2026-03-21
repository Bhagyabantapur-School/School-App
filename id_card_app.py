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

# --- IMPORT THE SCANNER ---
try:
    from streamlit_qrcode_scanner import qrcode_scanner
except ImportError:
    st.error("Please add 'streamlit-qrcode-scanner' to your requirements.txt")
    st.stop()

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS Digital - ID Generator", page_icon="🏫", layout="wide")

if 'attendance_log' not in st.session_state:
    st.session_state['attendance_log'] = pd.DataFrame(columns=['Time', 'Name', 'Roll', 'Class', 'Status', 'MDM'])

# --- 2. GOOGLE CREDENTIALS & DRIVE CONNECTIONS ---
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
        st.error("⚠️ Google Sheets Connection Failed! Please check your Streamlit Secrets.")
        st.stop()

sh = init_gsheets()

# --- 3. HELPER FUNCTIONS ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    """Securely downloads high-res images for the PDF generator."""
    try:
        creds = get_google_credentials()
        authed_session = AuthorizedSession(creds)
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        response = authed_session.get(url)
        return response.content if response.status_code == 200 else None
    except:
        return None

def extract_drive_id(url):
    """Extracts Drive ID for high-res PDF photos."""
    if pd.isna(url) or not isinstance(url, str) or "drive.google.com" not in url: return None
    if "/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    return None

def make_drive_image_url(url):
    """Converts Drive link to a direct-stream link for Streamlit Thumbnails."""
    if pd.isna(url) or not isinstance(url, str) or "drive.google.com" not in url: return url
    if "/d/" in url:
        file_id = url.split("/d/")[1].split("/")[0]
        return f"https://drive.google.com/uc?id={file_id}"
    return url

@st.cache_data(ttl=60) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}, inplace=True)
        return df
    except:
        return pd.DataFrame()

def clear_sheet_cache():
    fetch_sheet_data.clear()

def append_sheet_df(sheet_name, df):
    """Appends data for the MDM Scanner."""
    if df.empty: return
    try: 
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    
    df = df.fillna("").astype(str)
    try:
        ws.append_rows(df.values.tolist())
        clear_sheet_cache()
    except Exception as e:
        st.error(f"⚠️ Cloud sync error: {e}")

def update_photo_status_in_cloud(student_name, roll, student_class):
    """Logs manual photo checks from the Explorer Tab."""
    try:
        log_ws = sh.worksheet("photo_log")
        log_ws.append_row([datetime.now().strftime("%d-%m-%Y"), student_class, roll, student_name, "Taken"])
        clear_sheet_cache()
    except:
        st.error("Cloud update failed. Ensure 'photo_log' sheet exists in BPS_Database.")

def parse_qr_data(qr_string):
    try:
        data = {}
        parts = qr_string.split('|')
        for part in parts:
            if ':' in part:
                key, value = part.split(':', 1)
                data[key.strip()] = value.strip()
        return data
    except:
        return None

# --- 4. ORIGINAL LANDSCAPE PDF GENERATOR ---
def generate_pdf(students_list, photo_dict):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    x_start, y_start, card_w, card_h, gap = 10, 10, 86, 54, 8
    col, row = 0, 0
    
    bg_img = None
    for ext in ['background.jpg', 'background.jpeg', 'background.png']:
        if os.path.exists(ext):
            bg_img = ext
            break
            
    for student in students_list:
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # --- 1. FULL CARD BACKGROUND IMAGE ---
        if bg_img:
            try: pdf.image(bg_img, x=x, y=y, w=card_w, h=card_h)
            except: pass 

        # --- 2. Draw Card Border & Darker Blue Header ---
        pdf.set_draw_color(0, 0, 0); pdf.set_line_width(0.3); pdf.rect(x, y, card_w, card_h)
        pdf.set_fill_color(0, 51, 153); pdf.rect(x, y, card_w, 11, 'F')
        
        # --- LOGO ON THE RIGHT SIDE ---
        if os.path.exists('logo.png'): 
            pdf.image('logo.png', x=x+68.5, y=y+1, w=16, h=16)
            
        pdf.set_font("Arial", 'B', 8.5); pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x+2, y+1.5); pdf.cell(66, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x+2, y+6.5); pdf.cell(66, 3, "Mob: 7908390822  |  ID CARD - SESSION 2026", 0, 1, 'C')
        
        # --- PHOTO ---
        photo_x, photo_y, photo_w, photo_h = x+3, y+14, 18, 22
        student_id = str(student.get('Sl', 0)) + "_" + str(student.get('Roll', '0'))
        
        if student_id in photo_dict and photo_dict[student_id] is not None:
            temp_path = tempfile.mktemp(suffix=".jpg")
            with open(temp_path, "wb") as f: f.write(photo_dict[student_id])
            try:
                pdf.image(temp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
                pdf.set_draw_color(0, 0, 0); pdf.rect(photo_x, photo_y, photo_w, photo_h)
            except: pass
        else:
            pdf.set_draw_color(200); pdf.rect(photo_x, photo_y, photo_w, photo_h) 
            pdf.set_text_color(150); pdf.set_font("Arial", '', 5)
            pdf.set_xy(photo_x, y+20); pdf.cell(photo_w, 5, "NO PHOTO", 0, 0, 'C')
        
        # --- STUDENT DETAILS ---
        pdf.set_text_color(0); detail_x, curr_y, line_h = x+24, y+14, 4
        pdf.set_font("Arial", 'B', 9); pdf.set_xy(detail_x, curr_y)
        pdf.cell(44, line_h, f"{student.get('Name', '')}".upper()[:25], 0, 1); curr_y += 4.5
        pdf.set_font("Arial", '', 7)
        
        for label, val in [
            ("Father", str(student.get('Father', ''))[:22]), 
            ("Mother", str(student.get('Mother', ''))[:22]), 
            ("Class", f"{student.get('Class', '')} | Sec: {student.get('Section', 'A')}"), 
            ("DOB", student.get('DOB', ''))
        ]:
            pdf.set_xy(detail_x, curr_y); pdf.cell(44, line_h, f"{label}: {val}", 0, 1); curr_y += line_h
            
        pdf.set_xy(detail_x, curr_y); pdf.set_font("Arial", 'B', 7)
        pdf.cell(44, line_h, f"Mob: {student.get('Mobile', '')}", 0, 1)

        # --- QR CODE ---
        qr_data = f"Name:{student.get('Name', '')}|Roll:{student.get('Roll', '')}|Mob:{student.get('Mobile', '')}"
        qr = qrcode.make(qr_data); qr_path = tempfile.mktemp(suffix=".png"); qr.save(qr_path)
        pdf.image(qr_path, x=x+4.5, y=y+37, w=15, h=15)
        
        # --- FOOTER IMAGE ---
        if os.path.exists('image_2.png'):
            try: pdf.image('image_2.png', x=x, y=y+44, w=card_w, h=10)
            except: pass

        # --- WATERMARK & SIGNATURE ---
        wm_x, wm_y = x + 55, y + 42
        pdf.set_draw_color(220, 240, 255); pdf.set_line_width(0.4)
        pdf.line(wm_x, wm_y, wm_x, wm_y + 6); pdf.line(wm_x, wm_y, wm_x + 2, wm_y); pdf.line(wm_x, wm_y + 6, wm_x + 2, wm_y + 6)
        pdf.line(wm_x + 27, wm_y, wm_x + 27, wm_y + 6); pdf.line(wm_x + 25, wm_y, wm_x + 27, wm_y); pdf.line(wm_x + 25, wm_y + 6, wm_x + 27, wm_y + 6)

        pdf.set_text_color(210, 235, 255); pdf.set_font("Arial", 'B', 6); pdf.set_xy(wm_x, wm_y + 1); pdf.cell(27, 4, "BPS DIGITAL", 0, 0, 'C')

        if os.path.exists('signature.png'): 
            try: pdf.image('signature.png', x=x+58, y=y+40, w=22, h=8)
            except: pass
        
        # --- FOOTER TEXT ---
        pdf.set_text_color(0); pdf.set_font("Arial", 'I', 6); pdf.set_xy(x, y+49); pdf.cell(card_w-5, 3, "Sukhamay Kisku", 0, 1, 'R')
        pdf.set_font("Arial", '', 5); pdf.set_xy(x, y+51); pdf.cell(card_w-5, 2, "Head Teacher", 0, 0, 'R')
        
        # 2 Columns x 5 Rows = 10 Cards Per Page
        col += 1
        if col >= 2: col, row = 0, row + 1
        if row >= 5: pdf.add_page(); col, row = 0, 0
            
    # --- STREAMLIT CLOUD FPDF FIX ---
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    else:
        return bytes(pdf_output)

# --- 5. MAIN APP LAYOUT ---
tabs = st.tabs(["🖨️ ID Generator", "📸 Scanner", "📂 Database Explorer"])

# ==========================================
# TAB 1: ID GENERATOR
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
            
            edited_df = st.data_editor(
                print_ready[['Select', 'Roll', 'Name', 'Class', 'Section', 'Photo_URL']],
                hide_index=True, use_container_width=True, key="gen_editor",
                disabled=['Roll', 'Name', 'Class', 'Section', 'Photo_URL']
            )
            
            selected_students = print_ready.loc[edited_df[edited_df["Select"] == True].index].copy()

            if not selected_students.empty:
                num_students = len(selected_students)
                pages_needed = math.ceil(num_students / 10) # 10 cards per page
                
                st.divider()
                st.info(f"🖨️ **Print Summary:** You have selected **{num_students}** students. You will need **{pages_needed}** A4 paper(s) loaded into the printer (10 cards per page).")
                
                if st.button("Generate Secure PDF", type="primary"):
                    photo_dict = {}
                    my_bar = st.progress(0, text="Fetching Secure Photos from Google Drive...")
                    
                    for idx, (index, student) in enumerate(selected_students.iterrows()):
                        sid = str(student.get('Sl', index)) + "_" + str(student.get('Roll', '0'))
                        photo_url = str(student.get('Photo_URL', ''))
                        
                        drive_id = extract_drive_id(photo_url)
                        if drive_id:
                            img_bytes = fetch_secure_image_bytes(drive_id)
                            if img_bytes:
                                photo_dict[sid] = img_bytes
                                
                        my_bar.progress((idx + 1) / num_students, text=f"Fetched photo {idx + 1} of {num_students}")
                    
                    my_bar.empty()
                    
                    with st.spinner("Compiling PDF Document..."):
                        pdf_bytes = generate_pdf(selected_students.to_dict('records'), photo_dict)
                        
                    st.balloons()
                    st.download_button("📥 Download ID Cards (PDF)", pdf_bytes, f"BPS_ID_Cards_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf")
        else:
            st.info("No students found with a linked Photo URL and a cleared form.")

# ==========================================
# TAB 2: MDM SCANNER
# ==========================================
with tabs[1]:
    st.markdown('<h3 style="text-align:center; color:#28a745;">📸 Scan ID Card</h3>', unsafe_allow_html=True)
    st.write("Scanned data will sync directly to the main BPS Cloud Database!")
    
    qr_code = qrcode_scanner(key='mdm_scanner')
    
    if qr_code:
        data = parse_qr_data(qr_code)
        if data:
            student_name = data.get('Name', 'Unknown')
            student_class = data.get('Class', 'Unknown')
            student_roll = data.get('Roll', 'Unknown')
            
            existing = st.session_state['attendance_log'][
                (st.session_state['attendance_log']['Name'] == student_name) & 
                (st.session_state['attendance_log']['Roll'] == student_roll)
            ]
            
            if not existing.empty:
                st.warning(f"⚠️ {student_name} is already marked present today!")
            else:
                curr_date_str = datetime.now().strftime("%d-%m-%Y")
                curr_time_str = datetime.now().strftime("%H:%M")
                
                new_entry = pd.DataFrame([{
                    'Time': curr_time_str, 'Name': student_name, 'Roll': student_roll, 
                    'Class': student_class, 'Status': 'Present', 'MDM': 'Yes'
                }])
                st.session_state['attendance_log'] = pd.concat([st.session_state['attendance_log'], new_entry], ignore_index=True)
                
                mdm_data = pd.DataFrame([{
                    'Date': curr_date_str, 'Teacher': 'Scanned via ID App', 
                    'Class': student_class, 'Section': 'A', 'Roll': student_roll, 
                    'Name': student_name, 'Time': curr_time_str
                }])
                append_sheet_df('mdm_log', mdm_data)

                att_data = pd.DataFrame([{
                    'Date': curr_date_str, 'Class': student_class, 'Section': 'A', 
                    'Roll': student_roll, 'Name': student_name, 'Status': True
                }])
                append_sheet_df('student_attendance_master', att_data)

                st.success(f"✅ **{student_name}** logged & synced to Cloud!")
        else:
            st.error("Invalid QR Code Format. Please scan a valid BPS ID Card.")

    st.divider()
    st.markdown("### 📋 Today's Local Scans")
    if not st.session_state['attendance_log'].empty:
        st.dataframe(st.session_state['attendance_log'], use_container_width=True)
    else:
        st.info("No students scanned yet today.")

# ==========================================
# TAB 3: DATABASE EXPLORER
# ==========================================
with tabs[2]:
    st.subheader("📂 Student Database & Media Tracker")
    
    df_m = fetch_sheet_data("students_master")
    df_l = fetch_sheet_data("form_distribution_log")
    
    if not df_m.empty and not df_l.empty:
        df_m['Roll'] = df_m['Roll'].astype(str)
        df_l['Roll'] = df_l['Roll'].astype(str)
        
        explorer_db = pd.merge(df_m, df_l, on=['Class', 'Section', 'Roll'], how='left')
        
        if 'Thumb_URL' in explorer_db.columns:
            explorer_db['Display_Thumb'] = explorer_db['Thumb_URL'].apply(make_drive_image_url)
        else:
            explorer_db['Display_Thumb'] = None

        explorer_db['Photo_Link'] = explorer_db['Photo_URL'].apply(lambda x: True if pd.notna(x) and "drive" in str(x) else False)
        explorer_db['Form_OK'] = explorer_db['Return Status'].apply(lambda x: True if str(x) == "Complete" else False)
        explorer_db['Verified'] = explorer_db['Data Corrected'].apply(lambda x: True if str(x) == "Yes" else False)
        explorer_db['Photo Taken'] = False 

        cat_filter = st.selectbox("Filter Students:", ["All Students", "Missing Photo Link", "Form Pending"])
        
        filtered_view = explorer_db.copy()
        if cat_filter == "Missing Photo Link":
            filtered_view = filtered_view[filtered_view['Photo_Link'] == False]
        elif cat_filter == "Form Pending":
            filtered_view = filtered_view[filtered_view['Form_OK'] == False]

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
                st.success(f"Synced {len(taken_list)} records to Cloud!")
                st.rerun()
