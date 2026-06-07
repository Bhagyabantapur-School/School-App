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

# Set Timezone for Haldia, West Bengal
IST = pytz.timezone('Asia/Kolkata')

st.set_page_config(page_title="BPS Library Manager", page_icon="📚", layout="centered")

# --- BACK BUTTON (STRICTLY REQUIRED) ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("bps_dashboard.py")
st.write("---") 
# ---------------------------------------

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
    # Convert dict values to list in the correct order based on sheet headers
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

tabs = st.tabs(["Add Books & QR", "Issue Book", "Returns & Reminders"])

# ==========================================
# TAB 1: ADD BOOKS & GENERATE QR PDF
# ==========================================
with tabs[0]:
    st.header("Add New Books")
    
    with st.form("add_book_form"):
        col1, col2 = st.columns(2)
        title = col1.text_input("Book Title")
        author = col2.text_input("Author")
        
        if st.form_submit_button("Add to Library"):
            if title:
                # Generate a unique Book ID (e.g., BPS-B001)
                next_id_num = len(df_books) + 1 if not df_books.empty else 1
                book_id = f"BPS-B{next_id_num:03d}"
                
                # Capture accurate IST Date and Time
                now_ist = datetime.now(IST)
                today_date = now_ist.strftime("%Y-%m-%d")
                current_time = now_ist.strftime("%I:%M:%S %p")
                
                append_to_sheet("Books", {
                    "Book_ID": book_id,
                    "Title": title,
                    "Author": author,
                    "QR_Generated": "Yes",
                    "Date": today_date,
                    "Time": current_time
                })
                st.success(f"Added '{title}' with ID: {book_id} at {current_time}")
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
        
        # --- PDF GENERATION LOGIC ---
        if st.button("Generate A4 PDF for Printing"):
            with st.spinner("Generating PDF layout..."):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_auto_page_break(auto=False)
                pdf.add_page()
                pdf.set_font("helvetica", size=8)
                
                # A4 Grid settings
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
                    
                    # Save QR temporarily to place in PDF
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        qr.save(tmp.name)
                        # Place image and text
                        pdf.image(tmp.name, x=x, y=y, w=40, h=40)
                        pdf.set_xy(x, y + 40)
                        pdf.cell(40, 5, txt=str(row['Book_ID']), align='C')
                        
                    os.unlink(tmp.name) # Clean up temp file
                    
                    # Move to next grid position
                    col_count += 1
                    x += col_width
                    
                    if col_count >= 4: # 4 columns
                        col_count = 0
                        x = margin_x
                        row_count += 1
                        y += row_height
                        
                    if row_count >= 6: # 6 rows (24 total per page)
                        pdf.add_page()
                        row_count = 0
                        col_count = 0
                        x = margin_x
                        y = margin_y
                
                # Output PDF to Streamlit
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
# TAB 2: ISSUE BOOK (SCAN & SELECT)
# ==========================================
with tabs[1]:
    st.header("Scan & Issue Book")
    
    # 1. Scan QR Code
    scanned_book_id = qrcode_scanner(key='scanner_issue')
    
    if scanned_book_id:
        # Check if book exists
        if not df_books.empty and scanned_book_id in df_books['Book_ID'].values:
            book_details = df_books[df_books['Book_ID'] == scanned_book_id].iloc[0]
            st.success(f"📖 Scanned: {book_details['Title']} ({scanned_book_id})")
            
            # Check if already issued
            is_issued = False
            if not df_logs.empty:
                active_logs = df_logs[(df_logs['Book_ID'] == scanned_book_id) & (df_logs['Status'] == "Issued")]
                if not active_logs.empty:
                    is_issued = True
                    st.error(f"This book is currently issued to {active_logs.iloc[0]['Student_Name']} and has not been returned.")

            if not is_issued:
                st.markdown("### Select Student")
                
                # 2. Dynamic Dropdowns based on students_master
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
                                    "Book_ID": scanned_book_id,
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
                                st.rerun()
        else:
            st.error("Invalid QR Code or Book not found in database.")

# ==========================================
# TAB 3: RETURNS & REMINDERS
# ==========================================
with tabs[2]:
    st.header("Returns & 7-Day Reminders")
    
    if not df_logs.empty:
        # Filter only active issues
        issued_books = df_logs[df_logs['Status'] == "Issued"].copy()
        
        if not issued_books.empty:
            # Convert string dates to datetime objects for comparison
            issued_books['Due_Date_Obj'] = pd.to_datetime(issued_books['Due_Date'])
            today = pd.to_datetime(datetime.now(IST).strftime("%Y-%m-%d"))
            
            # Separate into overdue and on-time
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
