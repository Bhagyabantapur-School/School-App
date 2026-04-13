import streamlit as st
from datetime import date
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import tempfile
import os

# Page Config
st.set_page_config(page_title="Leave App - BPS Digital", layout="centered")

# --- CONFIGURATION SIDEBAR ---
st.sidebar.header("⚙️ App Settings")
st.sidebar.markdown("Enter your Google Sheet link below to enable automatic logging.")
sheet_url_input = st.sidebar.text_input("Google Sheet URL", placeholder="https://docs.google.com/spreadsheets/d/...")
st.sidebar.divider()
# -----------------------------

st.title("📝 Leave Application & Logger")
st.markdown("Select teacher, generate PDF, and log to Google Sheet.")
st.divider()

# Teacher List
TEACHER_LIST = [
    "SUKHAMAY KISKU", "UDAY NARAYAN JANA", "SUSMITA PAUL", 
    "TAPASI RANA", "BIMAL KUMAR PATRA", "SUJATA BISWAS ROTHA", 
    "TAPAN KUMAR MANDAL", "ROHINI SINGH", "MANJUMA KHATUN"
]

# Connect using the exact header name from your secrets.toml
conn = st.connection("gcp_service_account", type=GSheetsConnection)

# Application Form
with st.form("leave_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        applicant_name = st.selectbox("Select Teacher Name", TEACHER_LIST)
        designation = st.selectbox("Designation", ["A.T", "H.T"])
        leave_type = st.selectbox("Type of Leave", ["Casual Leave", "Medical Leave", "Commuted Leave"])
        num_days = st.number_input("Number of Days", min_value=1, step=1)
        
    with col2:
        start_date = st.date_input("From Date")
        end_date = st.date_input("To Date")
        reason_type = st.selectbox("Reason", ["Personal Affairs", "Medical Affairs", "Other"])
        
        if reason_type == "Other":
            reason = st.text_input("Specify Reason")
        else:
            reason = reason_type
            
        app_date = st.date_input("Date of Application", value=date.today())

    submitted = st.form_submit_button("Generate & Log Leave", type="primary")

# PDF Generation Function (A4 Size)
def create_pdf(name, desig, l_type, n_days, start, end, rsn, app_dt):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.cell(0, 6, txt="To,", ln=1)
    pdf.cell(0, 6, txt="The Chairman,", ln=1)
    pdf.cell(0, 6, txt="Purba Medinipur District Primary School Council,", ln=1)
    pdf.cell(0, 6, txt="P.O. Tamluk, Dist - Purba Medinipur", ln=1)
    pdf.ln(6)
    pdf.cell(0, 6, txt="Through The Proper Channel.", ln=1)
    pdf.ln(6)
    
    # Subject
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 6, txt=f"Subject: Prayer for {l_type} for {n_days} days.", ln=1)
    pdf.set_font("Arial", size=12)
    pdf.ln(6)
    
    pdf.cell(0, 6, txt="Respected Sir/Ma'am,", ln=1)
    pdf.ln(4)
    
    # Body
    body = (f"Most respectfully I beg to state that I am {name}, {desig} of "
            f"Khanjanchak Dhananjoy Primary School. P.O- Khanjanchak under Haldia Circle. "
            f"\n\nI could not attend school on & from {start} to {end} on account of my {rsn}. "
            f"\n\nI request you to grant my {l_type} for those days and consider my prayer to sanction leave and oblige.")
    pdf.multi_cell(0, 6, txt=body)
    pdf.ln(6)
    pdf.cell(0, 6, txt="Expecting your kind-hearted co-operation.", ln=1)
    pdf.ln(4)
    pdf.cell(0, 6, txt="Thanking you.", ln=1)
    pdf.ln(15)
    
    # Footer
    y_pos = pdf.get_y()
    pdf.set_x(20)
    pdf.cell(80, 6, txt="Place: Khanjanchak")
    pdf.set_x(110)
    pdf.cell(80, 6, txt="Yours Faithfully,", ln=1)
    pdf.set_x(20)
    pdf.cell(80, 6, txt=f"Date: {app_dt}")
    pdf.set_x(110)
    pdf.cell(80, 15, txt="", ln=1) # Space for sign
    pdf.set_x(110)
    pdf.cell(80, 6, txt=f"{name}", ln=1)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            pdf_bytes = f.read()
    os.remove(tmp.name)
    return pdf_bytes

if submitted:
    # 1. Log to Google Sheets
    if sheet_url_input.strip() == "":
        st.warning("⚠️ Google Sheet URL is missing. The PDF will be generated, but data will NOT be logged. Please paste the link in the sidebar.")
    else:
        new_data = pd.DataFrame([{
            "Date": app_date.strftime("%d-%m-%Y"),
            "Teacher": applicant_name,
            "Leave Type": leave_type,
            "Days": num_days,
            "From": start_date.strftime("%d-%m-%Y"),
            "To": end_date.strftime("%d-%m-%Y"),
            "Reason": reason
        }])
        
        try:
            # Pass the URL from the sidebar directly to the read and update methods
            existing_data = conn.read(spreadsheet=sheet_url_input, worksheet="Leaves", ttl=0)
            updated_df = pd.concat([existing_data, new_data], ignore_index=True)
            conn.update(spreadsheet=sheet_url_input, worksheet="Leaves", data=updated_df)
            st.success("📊 Leave successfully logged to Google Sheets.")
        except Exception as e:
            st.error(f"⚠️ Google Sheet log failed. Please check the URL and permissions. Error: {e}")

    # 2. PDF Generation
    pdf_file = create_pdf(applicant_name, designation, leave_type, num_days, 
                          start_date.strftime("%d-%m-%Y"), end_date.strftime("%d-%m-%Y"), 
                          reason, app_date.strftime("%d-%m-%Y"))
    
    st.success(f"✅ Leave application for {applicant_name} is ready to download!")
    
    # Download Button
    st.download_button(
        label="📥 Download A4 PDF for Print",
        data=pdf_file,
        file_name=f"Leave_{applicant_name.replace(' ', '_')}_{app_date.strftime('%d-%m-%Y')}.pdf",
        mime="application/pdf",
        type="primary"
    )
