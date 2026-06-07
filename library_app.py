import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import qrcode
import math
from datetime import datetime, timedelta
import pytz
from streamlit_qrcode_scanner import qrcode_scanner
from fpdf import FPDF
import tempfile
import os
import requests
import base64

# Set Timezone for Haldia, West Bengal
IST = pytz.timezone('Asia/Kolkata')

st.set_page_config(page_title="BPS Library Manager", page_icon="📚", layout="centered")

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if 'lib_scan_msg' not in st.session_state: st.session_state.lib_scan_msg = None
if 'scanned_book_id' not in st.session_state: st.session_state.scanned_book_id = None

# ==========================================
# 1. DATABASE CONNECTION
# ==========================================
@st.cache_resource
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

client = get_gspread_client()

# Connect to Sheets
@st.cache_data(ttl=60)
def load_students():
    try:
        # Target students_master
        sheet = client.open("BPS_Database").worksheet("students_master")
        df = pd.DataFrame(sheet.get_all_records())
        # Automatically capitalize headers (e.g., 'class' becomes 'Class') to prevent errors
        df.columns = [str(c).strip().title() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame(columns=["Class", "Section", "Name"])

def load_sheet_data(worksheet_name):
    try:
        sheet = client.open("Library_Database").worksheet(worksheet_name)
        records = sheet.get_all_records()
        return pd.DataFrame(records) if records else pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading {worksheet_name}: {e}")
        return pd.DataFrame()

def append_to_sheet(worksheet_name, data_dict):
    sheet = client.open("Library_Database").worksheet(worksheet_name)
    headers = sheet.row_values(1)
    row_to_insert = [str(data_dict.get(header, "")) for header in headers]
    sheet.append_row(row_to_insert)

def update_log_status(book_id, student_name):
    sheet = client.open("Library_Database").worksheet("Logs")
    records = sheet.get_all_records()
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    
    # Find the active log entry and update it
    for idx, row in enumerate(records):
        if str(row["Book_ID"]) == str(book_id) and row["Student_Name"] == student_name and row["Status"] == "Issued":
            sheet.update_cell(idx + 2, 7, today_str) # Return_Date is col 7
            sheet.update_cell(idx + 2, 8, "Returned") # Status is col 8
            break

st.title("📚 BPS Library Manager")

# Load data
df_students = load_students()
df_books = load_sheet_data("Books")
df_logs = load_sheet_data("Logs")

# --- NAVIGATION MENU (Now with 5 options) ---
menu_choice = st.selectbox(
    "📌 Main Menu", 
    ["Add Books & QR", "Issue Book", "Returns & Reminders", "All Books Inventory", "Book Details & Cover"]
)
st.markdown("---")

# ==========================================
# PAGE 1: ADD BOOKS & GENERATE QR PDF
# ==========================================
if menu_choice == "Add Books & QR":
    st.header("Add New Books")
    
    col_form, col_cam = st.columns([1, 1])
    
    with col_cam:
        st.write("📷 Capture Book Cover")
        st.caption("Tip: Tap the 'Switch Camera' icon on your screen to use the rear camera!")
        book_photo = st.camera_input("Take a picture of the front page")
    
    with col_form:
        with st.form("add_book_form"):
            title = st.text_input("Book Title")
            author = st.text_input("Author")
            submit_btn = st.form_submit_button("Add to Library")
            
            if submit_btn:
                if title:
                    next_id_num = len(df_books) + 1 if not df_books.empty else 1
                    book_id = f"BPS-B{next_id_num:03d}"
                    
                    now_ist = datetime.now(IST)
                    today_date = now_ist.strftime("%Y-%m-%d")
                    current_time = now_ist.strftime("%I:%M:%S %p")
                    
                    image_url = "No Image"
                    
                    # Upload Image to ImgBB
                    if book_photo is not None:
                        with st.spinner("Uploading image..."):
                            try:
                                api_key = st.secrets["IMGBB_API_KEY"]
                                url = "https://api.imgbb.com/1/upload"
                                payload = {
                                    "key": api_key,
                                    "image": base64.b64encode(book_photo.getvalue()).decode("utf-8")
                                }
                                response = requests.post(url, payload)
                                
                                if response.status_code == 200:
                                    image_url = response.json()["data"]["url"]
                                else:
                                    # This will catch if the API key is wrong or expired!
                                    st.error(f"ImgBB API Error: {response.text}")
                                    st.stop() # Stops the app so you can read the error
                                    
                            except KeyError:
                                st.error("⚠️ IMGBB_API_KEY is missing from your Streamlit Secrets!")
                                st.stop() # Stops the app
                            except Exception as e:
                                st.error(f"Upload failed: {e}")
                                st.stop() # Stops the app
                    
                    append_to_sheet("Books", {
                        "Book_ID": book_id,
                        "Title": title,
                        "Author": author,
                        "QR_Generated": "Yes",
                        "Date": today_date,
                        "Time": current_time,
                        "Cover_Image_URL": image_url
                    })
                    
                    st.success(f"Added '{title}' with ID: {book_id}")
                    if image_url != "No Image":
                        st.success("Image successfully uploaded!")
                        
                    st.rerun()
                else:
                    st.error("Please enter a book title.")

    st.markdown("---")
    st.subheader("Generate & Print QR Codes")
    
    if not df_books.empty:
        total_books = len(df_books)
        qrs_per_page = 24
        total_pages = math.ceil(total_books / qrs_per_page)
        
        st.info(f"🖨️ **Printing Details:** You have {total_books} books. This will require **{total_pages}** A4 page(s) to print (24 stickers per page).")
        
        if st.button("Generate A4 PDF for Printing"):
            with st.spinner("Generating PDF layout..."):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_auto_page_break(auto=False)
                pdf.add_page()
                pdf.set_font("helvetica", size=8)
                
                col_width = 45
                row_height = 48
                margin_x = 15
                margin_y = 15
                x, y = margin_x, margin_y
                col_count = 0
                row_count = 0
                
                for idx, row in df_books.iterrows():
                    qr_data = str(row['Book_ID'])
                    qr = qrcode.make(qr_data)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        qr.save(tmp.name)
                        pdf.image(tmp.name, x=x, y=y, w=40, h=40)
                        pdf.set_xy(x, y + 40)
                        pdf.cell(40, 5, txt=str(row['Book_ID']), align='C')
                        
                    os.unlink(tmp.name)
                    
                    col_count += 1
                    x += col_width
                    
                    if col_count >= 4:
                        col_count = 0
                        x = margin_x
                        row_count += 1
                        y += row_height
                        
                    if row_count >= 6:
                        pdf.add_page()
                        row_count = 0
                        col_count = 0
                        x = margin_x
                        y = margin_y
                
                pdf_bytes = bytes(pdf.output())
                st.success("✅ PDF Generated Successfully!")
                st.download_button(
                    label="📥 Download PDF to Print",
                    data=pdf_bytes,
                    file_name=f"Library_QR_Codes_{datetime.now(IST).strftime('%d-%m-%Y')}.pdf",
                    mime="application/pdf"
                )
    else:
        st.write("No books in the library yet.")

# ==========================================
# PAGE 2: ISSUE BOOK (SCAN & SELECT)
# ==========================================
elif menu_choice == "Issue Book":
    st.header("Scan & Issue Book")
    
    st.write("📸 **Scan Book QR Code (Uses Rear Camera automatically if available):**")
    qv = qrcode_scanner(key='library_qr_scanner')
    
    if st.session_state.lib_scan_msg:
        st.success(st.session_state.lib_scan_msg)
        st.session_state.lib_scan_msg = None
        
    if qv:
        should_rerun = False
        if st.session_state.scanned_book_id != qv:
            st.session_state.scanned_book_id = qv
            st.session_state.lib_scan_msg = f"✅ Scanned Successfully: {qv}"
            should_rerun = True
            
        if should_rerun:
            st.rerun()

    if st.session_state.scanned_book_id:
        active_id = st.session_state.scanned_book_id
        
        if not df_books.empty and active_id in df_books['Book_ID'].values:
            book_details = df_books[df_books['Book_ID'] == active_id].iloc[0]
            
            col_img, col_info = st.columns([1, 2])
            
            with col_img:
                if "Cover_Image_URL" in book_details and str(book_details["Cover_Image_URL"]).startswith("http"):
                    st.image(book_details["Cover_Image_URL"], use_container_width=True)
                else:
                    st.info("No cover image")
                    
            with col_info:
                st.success(f"📖 Ready to Issue: {book_details['Title']}")
                st.write(f"**Author:** {book_details.get('Author', 'N/A')}")
                st.write(f"**ID:** {active_id}")
            
            is_issued = False
            if not df_logs.empty:
                active_logs = df_logs[(df_logs['Book_ID'] == active_id) & (df_logs['Status'] == "Issued")]
                if not active_logs.empty:
                    is_issued = True
                    st.error(f"This book is currently issued to {active_logs.iloc[0]['Student_Name']} and has not been returned.")

            if not is_issued:
                st.markdown("### Select Student")
                
                classes = ["Select Class"] + sorted(list(df_students['Class'].unique())) if not df_students.empty else ["Select Class"]
                sel_class = st.selectbox("Class", classes)
                
                if sel_class != "Select Class":
                    sections = ["Select Section"] + sorted(list(df_students[df_students['Class'] == sel_class]['Section'].unique()))
                    sel_sec = st.selectbox("Section", sections)
                    
                    if sel_sec != "Select Section":
                        students = ["Select Student"] + sorted(list(df_students[(df_students['Class'] == sel_class) & (df_students['Section'] == sel_sec)]['Name'].unique()))
                        sel_student = st.selectbox("Student Name", students)
                        
                        if sel_student != "Select Student":
                            if st.button("Confirm Issue"):
                                today = datetime.now(IST)
                                due_date = today + timedelta(days=7)
                                
                                log_data = {
                                    "Book_ID": active_id,
                                    "Student_Name": sel_student,
                                    "Class": sel_class,
                                    "Section": sel_sec,
                                    "Issue_Date": today.strftime("%Y-%m-%d"),
                                    "Due_Date": due_date.strftime("%Y-%m-%d"),
                                    "Return_Date": "",
                                    "Status": "Issued"
                                }
                                append_to_sheet("Logs", log_data)
                                st.success(f"Book issued to {sel_student}. Due back on {due_date.strftime('%d-%m-%Y')}.")
                                
                                st.session_state.scanned_book_id = None
                                st.rerun()
            
            if st.button("Cancel & Scan Another Book"):
                st.session_state.scanned_book_id = None
                st.rerun()
                
        else:
            st.error("Invalid QR Code or Book not found in database.")
            if st.button("Try Again"):
                st.session_state.scanned_book_id = None
                st.rerun()

# ==========================================
# PAGE 3: RETURNS & REMINDERS
# ==========================================
elif menu_choice == "Returns & Reminders":
    st.header("Returns & 7-Day Reminders")
    
    if not df_logs.empty:
        issued_books = df_logs[df_logs['Status'] == "Issued"].copy()
        
        if not issued_books.empty:
            issued_books['Due_Date_Obj'] = pd.to_datetime(issued_books['Due_Date'])
            today = pd.to_datetime(datetime.now(IST).strftime("%Y-%m-%d"))
            
            overdue = issued_books[issued_books['Due_Date_Obj'] < today]
            on_time = issued_books[issued_books['Due_Date_Obj'] >= today]
            
            if not overdue.empty:
                st.error(f"⚠️ {len(overdue)} Books Overdue!")
                for _, row in overdue.iterrows():
                    st.markdown(f"**{row['Student_Name']}** ({row['Class']}) - {row['Book_ID']} | Due: {row['Due_Date']}")
                    if st.button(f"Mark Returned ##{row['Book_ID']}", key=f"ret_over_{row['Book_ID']}_{row['Student_Name']}"):
                        update_log_status(row['Book_ID'], row['Student_Name'])
                        st.success("Returned!")
                        st.rerun()
                        
            st.markdown("---")
            st.subheader("Currently Issued")
            for _, row in on_time.iterrows():
                st.markdown(f"**{row['Student_Name']}** ({row['Class']}) - {row['Book_ID']} | Due: {row['Due_Date']}")
                if st.button(f"Mark Returned ##{row['Book_ID']}", key=f"ret_on_{row['Book_ID']}_{row['Student_Name']}"):
                    update_log_status(row['Book_ID'], row['Student_Name'])
                    st.success("Returned!")
                    st.rerun()
        else:
            st.success("All issued books have been returned.")
    else:
        st.write("No issue logs found.")

# ==========================================
# PAGE 4: ALL BOOKS INVENTORY
# ==========================================
elif menu_choice == "All Books Inventory":
    st.header("📚 All Books Inventory")
    
    if not df_books.empty:
        display_df = df_books.copy()
        
        if not df_logs.empty:
            active_issues = df_logs[df_logs['Status'] == "Issued"]
            issued_book_ids = active_issues['Book_ID'].tolist()
            
            display_df['Current Status'] = display_df['Book_ID'].apply(
                lambda x: "🔴 Issued" if x in issued_book_ids else "🟢 Available"
            )
        else:
            display_df['Current Status'] = "🟢 Available"
        
        if "Cover_Image_URL" in display_df.columns:
            display_df = display_df.drop(columns=["Cover_Image_URL"])
            
        cols = display_df.columns.tolist()
        if 'Current Status' in cols:
            cols.insert(2, cols.pop(cols.index('Current Status')))
            display_df = display_df[cols]
            
        search_term = st.text_input("🔍 Search by Book Title, Author, or ID...", "")
        
        if search_term:
            search_mask = (
                display_df['Title'].astype(str).str.contains(search_term, case=False, na=False) | 
                display_df['Author'].astype(str).str.contains(search_term, case=False, na=False) |
                display_df['Book_ID'].astype(str).str.contains(search_term, case=False, na=False)
            )
            display_df = display_df[search_mask]
            
        st.caption(f"Total Books Found: {len(display_df)}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No books have been added to the library yet.")

# ==========================================
# PAGE 5: BOOK DETAILS & COVER (NEW)
# ==========================================
elif menu_choice == "Book Details & Cover":
    st.header("📖 View Book Details")
    
    if not df_books.empty:
        # Create an easy-to-read list for the dropdown menu
        book_options = ["Select a book..."] + df_books.apply(lambda x: f"{x['Book_ID']} - {x['Title']}", axis=1).tolist()
        
        selected_book = st.selectbox("Choose a book from the library:", book_options)
        
        if selected_book != "Select a book...":
            # Extract the actual Book_ID from the dropdown selection
            selected_id = selected_book.split(" - ")[0]
            
            # Find the row with the matching Book_ID
            book_details = df_books[df_books['Book_ID'] == selected_id].iloc[0]
            
            st.markdown("---")
            col_img, col_info = st.columns([1, 2])
            
            # Left side: Display the cover image
            with col_img:
                if "Cover_Image_URL" in book_details and str(book_details["Cover_Image_URL"]).startswith("http"):
                    st.image(book_details["Cover_Image_URL"], use_container_width=True)
                else:
                    st.info("No cover image available for this book.")
            
            # Right side: Display the book details
            with col_info:
                st.subheader(book_details['Title'])
                st.write(f"**Author:** {book_details.get('Author', 'N/A')}")
                st.write(f"**Book ID:** {book_details['Book_ID']}")
                st.write(f"**Added On:** {book_details.get('Date', 'N/A')} at {book_details.get('Time', 'N/A')}")
                
                # Check the current status of the book from the Logs sheet
                is_issued = False
                if not df_logs.empty:
                    active_logs = df_logs[(df_logs['Book_ID'] == selected_id) & (df_logs['Status'] == "Issued")]
                    if not active_logs.empty:
                        is_issued = True
                        log_info = active_logs.iloc[0]
                        st.error(f"**Current Status:** 🔴 Issued")
                        st.write(f"**Issued To:** {log_info['Student_Name']} ({log_info['Class']} - {log_info['Section']})")
                        st.write(f"**Issue Date:** {log_info['Issue_Date']}")
                        st.write(f"**Due Date:** {log_info['Due_Date']}")
                
                if not is_issued:
                    st.success(f"**Current Status:** 🟢 Available on Shelf")
    else:
        st.info("No books have been added to the library yet.")
