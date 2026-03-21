import streamlit as st
import pandas as pd
import qrcode
import os
from fpdf import FPDF
import tempfile
from datetime import datetime

# --- 1. DATA SOURCE CONFIGURATION ---
# Replace this with your actual Google Sheet ID
SHEET_ID = "1A2B3C4D5E6F7G8H9I" # <--- PASTE YOUR ID HERE
SHEET_NAME = "students_master"
# This URL tells Google Sheets to export the "students_master" tab as a CSV
GSHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- IMPORT THE SCANNER ---
try:
    from streamlit_qrcode_scanner import qrcode_scanner
except ImportError:
    st.error("Please add 'streamlit-qrcode-scanner' to your requirements.txt")
    st.stop()

# --- 2. CONFIGURATION ---
st.set_page_config(page_title="BPS Digital - ID Generator", page_icon="🏫", layout="centered")

if 'attendance_log' not in st.session_state:
    st.session_state['attendance_log'] = pd.DataFrame(columns=['Time', 'Name', 'Roll', 'Class', 'Status', 'MDM'])

# --- 3. FETCH DATA FROM GOOGLE SHEETS ---
@st.cache_data(ttl=300) # Refresh data every 5 minutes
def get_students():
    try:
        df = pd.read_csv(GSHEET_CSV_URL)
        # Clean up Class names if needed
        if 'Class' in df.columns:
            df['Class'] = df['Class'].replace('CALSS IV', 'CLASS IV')
        
        # Fill empty values to prevent PDF errors
        df.fillna('N/A', inplace=True)
        return df
    except Exception as e:
        st.error(f"Error connecting to BPS_Database: {e}")
        return pd.DataFrame()

# --- 4. PDF DESIGN ---
class IDCardPDF(FPDF):
    def create_card(self, row, x, y):
        # Card Border
        self.rect(x, y, 54, 86)
        
        # Header (Blue Bar)
        self.set_fill_color(0, 51, 102)
        self.rect(x, y, 54, 15, 'F')
        
        # School Name
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 8)
        self.set_xy(x, y + 3)
        self.cell(54, 4, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        
        # Student Photo / Name
        self.set_text_color(0, 0, 0)
        self.set_font('Arial', 'B', 10)
        self.set_xy(x, y + 18)
        self.cell(54, 5, str(row['Name']).upper(), 0, 1, 'C')
        
        # QR Code Generation
        qr_content = f"BPS|{row['Name']}|{row['Roll']}|{row['Class']}"
        qr = qrcode.make(qr_content)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            qr.save(tmp.name)
            
            # --- LOGO/QR POSITIONING (16mm on Right) ---
            # Card Width (54) - Logo (16) - Margin (2) = 36
            self.image(tmp.name, x=x + 36, y=y + 28, w=16, h=16)
            os.unlink(tmp.name)

        # Student Details (Left Aligned)
        self.set_font('Arial', '', 8)
        details = [
            f"Class: {row['Class']}",
            f"Roll: {row['Roll']}",
            f"Father: {row['Father']}",
            f"DOB: {row['DOB']}",
            f"Mobile: {row['Mobile']}"
        ]
        
        curr_y = y + 28
        for detail in details:
            self.set_xy(x + 2, curr_y)
            # Limit width to 32mm so text doesn't hit the 16mm QR code on the right
            self.cell(32, 4, detail, 0, 1, 'L')
            curr_y += 4.5

# --- 5. APP UI ---
st.title("🏫 BPS ID Card & MDM System")

df = get_students()

if not df.empty:
    mode = st.sidebar.radio("Select Mode", ["Batch Generator", "MDM Scanner"])

    if mode == "Batch Generator":
        st.subheader("🖨️ Generate ID Cards")
        target_class = st.selectbox("Select Class", ["All"] + list(df['Class'].unique()))
        
        if st.button("Generate PDF"):
            pdf = IDCardPDF(unit='mm', format='A4')
            pdf.add_page()
            
            cards_df = df if target_class == "All" else df[df['Class'] == target_class]
            
            # Layout Logic
            x_start, y_start = 10, 10
            x, y = x_start, y_start
            count = 0
            
            for index, row in cards_df.iterrows():
                pdf.create_card(row, x, y)
                count += 1
                x += 60 # Horizontal gap
                
                if count % 3 == 0: # 3 cards per row
                    x = x_start
                    y += 95 # Vertical gap
                
                if count % 9 == 0: # 9 cards per page
                    pdf.add_page()
                    x, y = x_start, y_start
            
            pdf_output = pdf.output(dest='S').encode('latin1')
            st.download_button("📥 Download PDF", pdf_output, "BPS_ID_Cards.pdf", "application/pdf")

    elif mode == "MDM Scanner":
        st.subheader("📱 QR Attendance & MDM Log")
        scanned_data = qrcode_scanner(key="scanner")
        
        if scanned_data:
            if scanned_data.startswith("BPS|"):
                _, s_name, s_roll, s_class = scanned_data.split("|")
                
                # Prevent duplicate scans
                if s_name not in st.session_state['attendance_log']['Name'].values:
                    new_row = pd.DataFrame([{
                        'Time': datetime.now().strftime("%H:%M:%S"),
                        'Name': s_name,
                        'Roll': s_roll,
                        'Class': s_class,
                        'Status': 'Present',
                        'MDM': 'Yes'
                    }])
                    st.session_state['attendance_log'] = pd.concat([st.session_state['attendance_log'], new_row], ignore_index=True)
                    st.success(f"Done! {s_name} (Roll {s_roll}) logged.")
                else:
                    st.info(f"{s_name} already scanned.")
        
        st.table(st.session_state['attendance_log'])
