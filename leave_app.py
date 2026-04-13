import streamlit as st
from datetime import date
from fpdf import FPDF
import tempfile
import os

# Set page configuration
st.set_page_config(page_title="Leave Application Generator", layout="centered")

st.title("📝 Leave Application Generator")
st.markdown("Generate a formal leave application for **Purba Medinipur DPSC**.")
st.divider()

# Application Form
with st.form("leave_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        applicant_name = st.text_input("Applicant Name", placeholder="e.g., Sukhamay Kisku")
        designation = st.selectbox("Designation", ["A.T", "H.T"])
        leave_type = st.selectbox("Type of Leave", ["Casual Leave", "Medical Leave", "Commuted Leave"])
        num_days = st.number_input("Number of Days", min_value=1, step=1)
        
    with col2:
        start_date = st.date_input("From Date")
        end_date = st.date_input("To Date")
        reason_type = st.selectbox("Reason", ["Personal Affairs", "Medical Affairs", "Other"])
        
        # Allow custom reason if "Other" is selected
        if reason_type == "Other":
            reason = st.text_input("Specify Reason", placeholder="Enter specific reason...")
        else:
            reason = reason_type
            
        app_date = st.date_input("Date of Application", value=date.today())

    # Submit button
    submitted = st.form_submit_button("Generate Letter", type="primary")

# Function to generate the A4 PDF
def create_pdf(name, desig, l_type, n_days, start, end, rsn, app_dt):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    
    # Set default font
    pdf.set_font("Arial", size=12)
    
    # Top Block
    pdf.cell(0, 6, txt="To,", ln=1)
    pdf.cell(0, 6, txt="The Chairman,", ln=1)
    pdf.cell(0, 6, txt="Purba Medinipur District Primary School Council,", ln=1)
    pdf.cell(0, 6, txt="P.O. Tamluk, Dist - Purba Medinipur", ln=1)
    pdf.ln(6)
    
    pdf.cell(0, 6, txt="Through The Proper Channel.", ln=1)
    pdf.ln(6)
    
    # Subject (Bold)
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 6, txt=f"Subject: Prayer for {l_type} for {n_days} days.", ln=1)
    pdf.set_font("Arial", size=12)
    pdf.ln(6)
    
    # Salutation
    pdf.cell(0, 6, txt="Respected Sir/Ma'am,", ln=1)
    pdf.ln(4)
    
    # Body Paragraphs
    body1 = f"Most respectfully I beg to state that I am {name}, {desig} of Khanjanchak Dhananjoy Primary School. P.O- Khanjanchak under Haldia Circle."
    pdf.multi_cell(0, 6, txt=body1)
    pdf.ln(4)
    
    body2 = f"I could not attend school on & from {start} to {end} on account of my {rsn}."
    pdf.multi_cell(0, 6, txt=body2)
    pdf.ln(4)
    
    body3 = f"I request you to grant my {l_type} for those days and consider my prayer to sanction leave and oblige."
    pdf.multi_cell(0, 6, txt=body3)
    pdf.ln(4)
    
    pdf.cell(0, 6, txt="Expecting your kind-hearted co-operation.", ln=1)
    pdf.ln(4)
    
    pdf.cell(0, 6, txt="Thanking you.", ln=1)
    pdf.ln(15)
    
    # Footer Section (Place/Date on left, Signature on right)
    y_before = pdf.get_y()
    
    # Left Block
    pdf.set_y(y_before)
    pdf.set_x(20)
    pdf.cell(80, 6, txt="Place: Khanjanchak", ln=1)
    pdf.cell(80, 6, txt=f"Date: {app_dt}", ln=1)
    
    # Right Block
    pdf.set_y(y_before)
    pdf.set_x(110)
    pdf.cell(80, 6, txt="Yours Faithfully,", ln=1)
    pdf.set_x(110)
    pdf.cell(80, 10, txt="", ln=1) # Extra space for physical signature
    pdf.set_x(110)
    pdf.cell(80, 6, txt=f"{name}", ln=1)
    pdf.set_x(110)
    pdf.multi_cell(80, 6, txt=f"{desig} of Khanjanchak Dhananjoy Pry. School\nP.O- Khanjanchak, Haldia Circle")
    
    # Save securely to a temporary file and read as bytes
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            pdf_bytes = f.read()
            
    os.remove(tmp.name) # Cleanup temp file
    return pdf_bytes

# Process and Display after submission
if submitted:
    if not applicant_name.strip():
        st.error("⚠️ Please enter the Applicant Name to generate the letter.")
    else:
        # Format dates
        start_str = start_date.strftime("%d-%m-%Y")
        end_str = end_date.strftime("%d-%m-%Y")
        app_str = app_date.strftime("%d-%m-%Y")
        
        # 1. Generate Plain Text Version
        letter_text = f"""To,
The Chairman,
Purba Medinipur District Primary School Council,
P.O. Tamluk, Dist - Purba Medinipur

Through The Proper Channel.

Subject: Prayer for {leave_type} for {num_days} days.

Respected Sir/Ma'am,

Most respectfully I beg to state that I am {applicant_name}, {designation} of Khanjanchak Dhananjoy Primary School. P.O- Khanjanchak under Haldia Circle.

I could not attend school on & from {start_str} to {end_str} on account of my {reason}.

I request you to grant my {leave_type} for those days and consider my prayer to sanction leave and oblige.

Expecting your kind-hearted co-operation.

Thanking you.

Place: Khanjanchak
Date: {app_str}

Yours Faithfully,

{applicant_name}
{designation} of Khanjanchak Dhananjoy Pry. School
P.O- Khanjanchak, Haldia Circle
"""
        
        # 2. Generate PDF Version
        pdf_file = create_pdf(applicant_name, designation, leave_type, num_days, start_str, end_str, reason, app_str)
        
        st.success("✅ Letter generated successfully!")
        st.text_area("Preview (Text Version)", value=letter_text, height=300)
        
        # Download Buttons Side-by-Side
        dl_col1, dl_col2 = st.columns(2)
        
        with dl_col1:
            st.download_button(
                label="📄 Download as PDF (For Print)",
                data=pdf_file,
                file_name=f"Leave_Application_{applicant_name.replace(' ', '_')}.pdf",
                mime="application/pdf",
                type="primary"
            )
            
        with dl_col2:
            st.download_button(
                label="📝 Download as Text File",
                data=letter_text,
                file_name=f"Leave_Application_{applicant_name.replace(' ', '_')}.txt",
                mime="text/plain"
            )
